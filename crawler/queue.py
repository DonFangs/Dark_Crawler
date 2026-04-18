from typing import Optional, Tuple

from database.db import Database


class UrlQueue:
    """Simple queue logic for pending pages based on crawl depth."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def add_url(self, url: str, depth: int = 0) -> Tuple[int, bool]:
        """Add a URL to the pending queue at a specific depth."""
        return self.db.insert_page(url, crawl_depth=depth)

    def get_next_url(self) -> Optional[Tuple[int, str, int]]:
        """Return the next pending URL and its crawl depth."""
        pending = self.db.get_next_uncrawled(limit=1)
        return pending[0] if pending else None
