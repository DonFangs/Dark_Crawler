"""Dark Web transport for v0.2 with Tor connectivity verification and retries."""

import logging
import time
from typing import Optional

import requests
from requests.exceptions import RequestException

try:
    import socks  # type: ignore
except ImportError:  # pragma: no cover
    socks = None


class TransportError(RuntimeError):
    """Raised when a Tor transport request fails after retries."""


class DarkWebTransport:
    """Dark-web HTTP transport using Tor's SOCKS5 proxy."""

    def __init__(
        self,
        user_agent: Optional[str] = None,
        tor_proxy: str = "socks5h://127.0.0.1:9050",
    ) -> None:
        if socks is None:
            raise RuntimeError(
                "DarkWebTransport requires PySocks. Install it via `pip install requests[socks]` "
                "or `pip install pysocks`."
            )

        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": user_agent or "dark-crawler-tor/0.2",
            }
        )
        self.session.proxies.update(
            {
                "http": tor_proxy,
                "https": tor_proxy,
            }
        )
        self.logger = logging.getLogger(__name__)
        self.verify_tor_connection()

    def verify_tor_connection(self) -> None:
        """Verify that traffic is routing through Tor before crawling."""
        api_url = "https://check.torproject.org/api/ip"
        try:
            response = self.session.get(api_url, timeout=10)
            response.raise_for_status()
            payload = response.json()
            if not payload.get("IsTor"):
                raise RuntimeError(
                    "Tor is not running on 127.0.0.1:9050 or traffic is not routing through Tor. Start Tor first."
                )
            exit_ip = payload.get("IP")
            self.logger.info("Tor connectivity verified via exit IP %s", exit_ip)
        except Exception as exc:
            raise RuntimeError(
                "Tor is not running on 127.0.0.1:9050 or traffic is not routing through Tor. Start Tor first."
            ) from exc

    def get(self, url: str, timeout: float):
        """Fetch a URL through Tor with retry support."""
        backoffs = [2, 4, 8]
        last_exception: Optional[Exception] = None
        for attempt, wait in enumerate(backoffs, start=1):
            try:
                response = self.session.get(url, timeout=timeout, allow_redirects=True)
                status = response.status_code
                if 500 <= status < 600:
                    if attempt < len(backoffs):
                        self.logger.warning(
                            "Retry %s for %s after %s seconds due to server error %s",
                            attempt,
                            url,
                            wait,
                            status,
                        )
                        time.sleep(wait)
                        continue
                    raise TransportError(
                        f"Server error {status} when fetching {url}"
                    )
                return response
            except RequestException as exc:
                last_exception = exc
                if hasattr(exc, "response") and exc.response is not None:
                    status_code = exc.response.status_code
                    if 400 <= status_code < 500:
                        raise TransportError(
                            f"Client error {status_code} when fetching {url}"
                        ) from exc
                if attempt < len(backoffs):
                    self.logger.warning(
                        "Retry %s for %s after %s seconds due to error: %s",
                        attempt,
                        url,
                        wait,
                        exc,
                    )
                    time.sleep(wait)
                    continue
                raise TransportError(
                    f"Failed to fetch {url} after {attempt} attempts"
                ) from exc
        raise TransportError(
            f"Failed to fetch {url} after {len(backoffs)} attempts"
        ) from last_exception
