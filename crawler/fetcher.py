import logging
import time
from typing import Optional, Tuple

from requests import Response


class Fetcher:
    """Fetches pages using a pluggable transport."""

    def __init__(
        self,
        transport: object,
        delay_seconds: float = 2.0,
        timeout: float = 10.0,
    ) -> None:
        self.transport = transport
        self.delay_seconds = delay_seconds
        self.timeout = timeout
        self.logger = logging.getLogger(__name__)

    def fetch(
        self,
        url: str,
    ) -> Tuple[Optional[str], Optional[int], Optional[str], Optional[Response]]:
        """Fetch a URL and return HTML, status code, error, and response."""
        # Removed time.sleep(self.delay_seconds) to avoid double delay - rate limiting is handled by _apply_domain_rate_limit() in crawler.py
        try:
            response = self.transport.get(url, timeout=self.timeout)
            if response is None:
                # Handle non-HTML content (e.g., images, binaries) that transport skips
                return None, None, 'non-html-content-skipped', None
            return response.text, response.status_code, None, response
        except Exception as exc:
            self.logger.warning("Fetch error for %s: %s", url, exc)
            return None, None, str(exc), None
