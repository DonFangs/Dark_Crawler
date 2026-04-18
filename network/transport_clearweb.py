import requests

class ClearWebTransport:
    """
    Clear‑web HTTP transport for v0.1.
    This is the only implemented transport.
    The crawler calls transport.get(url, timeout=...).
    """

    def __init__(self, user_agent: str | None = None):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": user_agent or "v0.1-metadata-crawler"
        })

    def get(self, url: str, timeout: float):
        """
        Wrapper around requests.get.
        Returns a Response object.
        """
        return self.session.get(url, timeout=timeout, allow_redirects=True)
