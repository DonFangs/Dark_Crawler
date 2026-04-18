from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

class Parser:
    """
    Responsible for extracting metadata from HTML:
    - title
    - links
    """

    def extract_title(self, html: str) -> str | None:
        try:
            soup = BeautifulSoup(html, "html.parser")
            if soup.title and soup.title.string:
                return soup.title.string.strip()
        except Exception:
            pass
        return None

    def extract_links(self, html: str, base_url: str) -> list[str]:
        links: list[str] = []
        try:
            soup = BeautifulSoup(html, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                absolute = urljoin(base_url, href)
                # Normalize: only keep http/https for v0.1
                parsed = urlparse(absolute)
                if parsed.scheme in ("http", "https"):
                    links.append(absolute)
        except Exception:
            pass
        return list(set(links))  # dedupe
