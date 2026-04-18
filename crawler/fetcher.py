import time
import requests

class Fetcher:
    """
    Fetches pages using a pluggable transport.
    For v0.1 this uses clear‑web HTTP via requests.
    """

    def __init__(self, transport, delay_seconds: float = 2.0, timeout: float = 10.0):
        self.transport = transport
        self.delay_seconds = delay_seconds
        self.timeout = timeout

    def fetch(self, url: str):
        """
        Returns (html_text, status_code, error_message_or_None).
        """
        time.sleep(self.delay_seconds)  # keep it slow and gentle
        try:
            response = self.transport.get(url, timeout=self.timeout)
            return response.text, response.status_code, None
        except Exception as e:
            return None, None, str(e)
