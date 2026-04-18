import logging
import time
from typing import Optional

import requests
from requests.exceptions import RequestException


class TransportError(RuntimeError):
    """Raised when a transport request fails after retries."""


class ClearWebTransport:
    """Clear-web HTTP transport with retry and exponential backoff."""

    def __init__(self, user_agent: Optional[str] = None) -> None:
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": user_agent or "dark-crawler-clearweb/0.2",
            }
        )
        self.logger = logging.getLogger(__name__)

    def get(self, url: str, timeout: float):
        """Fetch a URL with retries on connection errors and 5xx failures."""
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
