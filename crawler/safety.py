import re

class Safety:
    """
    Safety filters for v0.1:
    - basic HTML sanity
    - captcha detection
    - URL sanity
    """

    CAPTCHA_KEYWORDS = [
        "captcha",
        "are you a robot",
        "verify you are human",
        "cloudflare",
        "challenge",
    ]

    def is_safe_html(self, html: str) -> bool:
        """
        v0.1: very minimal check.
        You can expand this later with more rules.
        """
        if not html or not isinstance(html, str):
            return False
        # Could add more filters here if needed.
        return True

    def is_captcha_page(self, html: str) -> bool:
        lower = html.lower()
        return any(keyword in lower for keyword in self.CAPTCHA_KEYWORDS)

    def is_potentially_valid_url(self, url: str) -> bool:
        # Very basic sanity check for v0.1
        if not url.startswith("http://") and not url.startswith("https://"):
            return False
        if len(url) > 2048:
            return False
        # crude filter to avoid obvious junk
        if re.search(r"\s", url):
            return False
        return True
