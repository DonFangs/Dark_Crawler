"""Dark Web transport for v0.1.

This transport sends HTTP(S) requests through a SOCKS5 proxy, which is the
standard way to route traffic through Tor for .onion addresses.

The crawler only depends on the transport having a compatible interface:
    transport.get(url, timeout=...)

Usage:
    from network.transport_darkweb import DarkWebTransport
    transport = DarkWebTransport()

By default this connects to Tor at 127.0.0.1:9050. You can override the
proxy URL if your Tor instance is running elsewhere.
"""

import requests

try:
    import socks  # type: ignore
except ImportError:  # pragma: no cover
    socks = None


class DarkWebTransport:
    """Dark-web HTTP transport using Tor's SOCKS5 proxy."""

    def __init__(self, user_agent: str | None = None, tor_proxy: str = "socks5h://127.0.0.1:9050"):
        if socks is None:
            raise RuntimeError(
                "DarkWebTransport requires PySocks. Install it via `pip install requests[socks]` "
                "or `pip install pysocks`."
            )

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": user_agent or "v0.1-darkweb-crawler"
        })
        self.session.proxies.update({
            "http": tor_proxy,
            "https": tor_proxy,
        })

    def get(self, url: str, timeout: float):
        """Fetch the given URL through Tor and return the Response object."""
        return self.session.get(url, timeout=timeout, allow_redirects=True)
