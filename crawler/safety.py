import logging
import re
from datetime import datetime, UTC
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup


class Safety:
    """Safety checks for captcha detection and URL validation."""

    CAPTCHA_KEYWORDS = [
        "captcha",
        "are you a robot",
        "verify you are human",
        "cloudflare",
        "challenge",
    ]

    CAPTCHA_DIV_CLASSES = [
        "cf-challenge",
        "g-recaptcha",
        "h-captcha",
        "captcha-container",
    ]

    def is_safe_html(self, html: str) -> bool:
        """Return True if the HTML is syntactically valid for crawling."""
        if not html or not isinstance(html, str):
            return False
        return True

    def is_captcha_page(self, html: str) -> bool:
        """Detect captcha pages based on HTML structure rather than raw keywords."""
        try:
            soup = BeautifulSoup(html, "html.parser")
            for noscript in soup.find_all("noscript"):
                if "captcha" in noscript.get_text(" ", strip=True).lower():
                    return True

            for form in soup.find_all("form"):
                for element in form.find_all(["input", "button", "iframe", "div", "span"]):
                    for attr in ("id", "name", "class", "type", "placeholder", "aria-label", "title", "value", "alt"):
                        value = element.get(attr)
                        if not value:
                            continue
                        if any(keyword in str(value).lower() for keyword in self.CAPTCHA_KEYWORDS):
                            return True

            for div in soup.find_all("div", class_=True):
                classes = " ".join(div.get("class", [])).lower()
                if any(keyword in classes for keyword in self.CAPTCHA_DIV_CLASSES):
                    return True
        except Exception as exc:
            logging.getLogger(__name__).warning("Captcha detection failed: %s", exc)
        return False

    def is_potentially_valid_url(self, url: str) -> bool:
        """Perform a lightweight URL sanity check."""
        if not url.startswith("http://") and not url.startswith("https://"):
            return False
        if len(url) > 2048:
            return False
        if re.search(r"\s", url):
            return False
        return True


class RobotsChecker:
    """Fetch and cache robots.txt rules for each domain."""

    def __init__(self, transport: object, cache_ttl_seconds: int = 3600, user_agent: str = "*") -> None:
        self.transport = transport
        self.cache_ttl_seconds = cache_ttl_seconds
        self.user_agent = user_agent
        self.logger = logging.getLogger(__name__)
        self.cache: Dict[str, Tuple[RobotFileParser, datetime]] = {}

    def is_allowed(self, url: str) -> bool:
        """Return True if the URL is allowed by robots.txt."""
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if not domain:
            return False

        parser = self._get_parser_for_domain(parsed.scheme, domain)
        return parser.can_fetch(self.user_agent, url)

    def _get_parser_for_domain(self, scheme: str, domain: str) -> RobotFileParser:
        cache_key = f"{scheme}://{domain}"
        entry = self.cache.get(cache_key)
        now = datetime.now(UTC)
        if entry and (now - entry[1]).total_seconds() < self.cache_ttl_seconds:
            return entry[0]

        robots_url = f"{scheme}://{domain}/robots.txt"
        parser = RobotFileParser()
        parser.set_url(robots_url)
        try:
            response = self.transport.get(robots_url, timeout=10)
            if response is not None and response.status_code == 200:
                parser.parse(response.text.splitlines())
            else:
                parser.allow_all = True
                self.logger.debug(
                    "Robots.txt not available for %s, allowing all by default.",
                    domain,
                )
        except Exception as exc:
            parser.allow_all = True
            self.logger.warning(
                "Failed to fetch robots.txt for %s: %s", domain, exc
            )

        self.cache[cache_key] = (parser, now)
        return parser
