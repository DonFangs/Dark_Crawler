from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup


class Parser:
    """Responsible for extracting metadata from HTML."""

    def extract_title(self, html: str) -> Optional[str]:
        try:
            soup = BeautifulSoup(html, "html.parser")
            if soup.title and soup.title.string:
                return soup.title.string.strip()
        except Exception:
            pass
        return None

    def extract_links(self, html: str, base_url: str) -> List[Tuple[str, str]]:
        """Extract unique links and their anchor text from HTML."""
        results: Dict[str, str] = {}
        try:
            soup = BeautifulSoup(html, "html.parser")
            for anchor in soup.find_all("a", href=True):
                href = anchor["href"].strip()
                absolute = urljoin(base_url, href)
                parsed = urlparse(absolute)
                if parsed.scheme not in ("http", "https"):
                    continue
                anchor_text = " ".join(anchor.stripped_strings).strip()[:500]
                results.setdefault(absolute, anchor_text)
        except Exception:
            pass
        return list(results.items())
