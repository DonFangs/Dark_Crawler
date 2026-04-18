from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin, urlparse, urlunparse, parse_qs, urlencode

from bs4 import BeautifulSoup


def normalize_url(url: str) -> str:
    """Normalize a URL for consistent storage and comparison.
    
    Strips fragments, removes trailing slashes, lowercases scheme/netloc,
    and sorts query parameters alphabetically.
    
    Args:
        url: URL to normalize.
        
    Returns:
        Normalized URL.
    """
    try:
        parsed = urlparse(url)
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()
        path = parsed.path
        
        if path and path != "/" and path.endswith("/"):
            path = path.rstrip("/")
        
        params = parse_qs(parsed.query, keep_blank_values=True)
        sorted_query = urlencode(
            sorted([(k, v[0] if isinstance(v, list) and v else v) for k, v in params.items()]),
            doseq=False
        )
        
        return urlunparse((scheme, netloc, path, "", sorted_query, ""))
    except Exception:
        return url



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
        """Extract unique links and their anchor text from HTML.
        
        Args:
            html: HTML content to parse.
            base_url: Base URL for resolving relative links.
            
        Returns:
            List of (url, anchor_text) tuples.
        """
        results: Dict[str, str] = {}
        try:
            soup = BeautifulSoup(html, "html.parser")
            for anchor in soup.find_all("a", href=True):
                href = anchor["href"].strip()
                absolute = urljoin(base_url, href)
                normalized = normalize_url(absolute)
                parsed = urlparse(normalized)
                if parsed.scheme not in ("http", "https"):
                    continue
                anchor_text = " ".join(anchor.stripped_strings).strip()[:500]
                results.setdefault(normalized, anchor_text)
        except Exception:
            pass
        return list(results.items())
