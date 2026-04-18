import json
import sqlite3
from datetime import datetime, UTC
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

SCHEMA_FILE = Path(__file__).with_name("schema.sql")


class Database:
    """Manages the SQLite schema and graph storage for the crawler."""

    def __init__(self, path: str):
        self.path = path
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON;")

    def init_schema(self) -> None:
        """Initialize the database schema and warn if an old schema exists."""
        with open(SCHEMA_FILE, "r", encoding="utf-8") as f:
            schema_sql = f.read()
        self.conn.executescript(schema_sql)
        self.conn.commit()
        self._warn_if_old_schema()

    def _warn_if_old_schema(self) -> None:
        cur = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
            ("sites",),
        )
        row = cur.fetchone()
        if row:
            import logging

            logging.getLogger(__name__).warning(
                "Detected legacy 'sites' table. The database schema has changed and should be recreated or migrated."
            )

    def get_or_create_domain(self, domain_str: str) -> Tuple[int, bool]:
        """Return the domain ID, creating the domain record if needed."""
        domain = domain_str.strip().lower()
        if not domain:
            raise ValueError("Domain must not be empty")

        is_onion = domain.endswith(".onion")
        onion_version: Optional[int] = None
        if is_onion:
            base_name = domain[: -len(".onion")]
            if len(base_name) == 16:
                onion_version = 2
            elif len(base_name) == 56:
                onion_version = 3

        now = datetime.now(UTC).isoformat()
        cur = self.conn.execute(
            "SELECT id FROM domains WHERE domain = ?",
            (domain,),
        )
        row = cur.fetchone()
        if row:
            return row["id"], False

        self.conn.execute(
            "INSERT INTO domains (domain, is_onion, onion_version, first_seen, last_seen, last_status, times_seen) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (domain, int(is_onion), onion_version, now, now, None, 1),
        )
        self.conn.commit()
        cur = self.conn.execute(
            "SELECT id FROM domains WHERE domain = ?",
            (domain,),
        )
        row = cur.fetchone()
        return row["id"], True

    def insert_page(
        self,
        url: str,
        crawl_depth: int = 0,
        session_id: Optional[int] = None,
    ) -> Tuple[int, bool]:
        """Insert a new page or return the existing page ID."""
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        if not domain:
            raise ValueError("URL must include a domain")

        domain_id, created_domain = self.get_or_create_domain(domain)
        now = datetime.now(UTC).isoformat()
        path = parsed.path or "/"
        self.conn.execute(
            "INSERT OR IGNORE INTO pages (domain_id, url, path, status, crawl_depth, first_seen, session_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (domain_id, url, path, "pending", crawl_depth, now, session_id),
        )
        self.conn.execute(
            "UPDATE pages SET crawl_depth = ? WHERE url = ? AND crawl_depth > ?",
            (crawl_depth, url, crawl_depth),
        )
        if not created_domain:
            self.conn.execute(
                "UPDATE domains SET last_seen = ?, times_seen = times_seen + 1 WHERE id = ?",
                (now, domain_id),
            )
        self.conn.commit()
        cur = self.conn.execute(
            "SELECT id FROM pages WHERE url = ?",
            (url,),
        )
        row = cur.fetchone()
        return row["id"], created_domain

    def insert_link(
        self,
        from_page_id: int,
        to_page_id: int,
        anchor_text: Optional[str] = None,
        session_id: Optional[int] = None,
    ) -> None:
        """Create a unique directed link between two pages."""
        discovered_at = datetime.now(UTC).isoformat()
        anchor_text = anchor_text.strip()[:500] if anchor_text else None
        self.conn.execute(
            "INSERT OR IGNORE INTO links (from_page_id, to_page_id, anchor_text, discovered_at, session_id) VALUES (?, ?, ?, ?, ?)",
            (from_page_id, to_page_id, anchor_text, discovered_at, session_id),
        )
        self.conn.commit()

    def start_crawl_session(
        self,
        transport_type: str,
        seed_urls: List[str],
        max_depth: int,
        max_pages: int,
    ) -> int:
        """Begin a new crawl session and return its session ID."""
        started_at = datetime.now(UTC).isoformat()
        seed_urls_json = json.dumps(seed_urls)
        cur = self.conn.execute(
            "INSERT INTO crawl_sessions (started_at, transport_type, seed_urls, max_depth, max_pages) VALUES (?, ?, ?, ?, ?)",
            (started_at, transport_type, seed_urls_json, max_depth, max_pages),
        )
        self.conn.commit()
        return cur.lastrowid

    def end_crawl_session(self, session_id: int, status: str = "completed") -> None:
        """Mark the crawl session as finished."""
        ended_at = datetime.now(UTC).isoformat()
        self.conn.execute(
            "UPDATE crawl_sessions SET ended_at = ?, status = ? WHERE id = ?",
            (ended_at, status, session_id),
        )
        self.conn.commit()

    def update_page_status(
        self,
        page_id: int,
        status: str,
        http_code: Optional[int] = None,
        content_hash: Optional[str] = None,
        page_size: Optional[int] = None,
        server_header: Optional[str] = None,
        title: Optional[str] = None,
    ) -> None:
        """Update a page record after an attempted crawl."""
        last_crawled = datetime.now(UTC).isoformat()
        self.conn.execute(
            "UPDATE pages SET status = ?, http_status_code = ?, content_hash = ?, page_size_bytes = ?, server_header = ?, title = ?, last_crawled = ?, crawl_count = crawl_count + 1 WHERE id = ?",
            (status, http_code, content_hash, page_size, server_header, title, last_crawled, page_id),
        )
        self.conn.commit()

    def get_next_uncrawled(self, limit: int = 10) -> List[Tuple[int, str, int]]:
        """Return pending pages ordered by crawl depth."""
        cur = self.conn.execute(
            "SELECT id, url, crawl_depth FROM pages WHERE status = 'pending' ORDER BY crawl_depth ASC, id ASC LIMIT ?",
            (limit,),
        )
        return [(row["id"], row["url"], row["crawl_depth"]) for row in cur.fetchall()]

    def get_domain_stats(self) -> Dict[str, int]:
        """Return aggregate domain statistics for the current dataset."""
        stats: Dict[str, int] = {}
        stats["total_domains"] = self.conn.execute(
            "SELECT COUNT(*) FROM domains"
        ).fetchone()[0]
        stats["alive"] = self.conn.execute(
            "SELECT COUNT(*) FROM domains WHERE last_status = 'alive'"
        ).fetchone()[0]
        stats["dead"] = self.conn.execute(
            "SELECT COUNT(*) FROM domains WHERE last_status = 'dead'"
        ).fetchone()[0]
        stats["onion_count"] = self.conn.execute(
            "SELECT COUNT(*) FROM domains WHERE is_onion = 1"
        ).fetchone()[0]
        stats["clearweb_count"] = self.conn.execute(
            "SELECT COUNT(*) FROM domains WHERE is_onion = 0"
        ).fetchone()[0]
        return stats

    def increment_crawl_session_stats(
        self,
        session_id: int,
        pages_crawled: int = 0,
        pages_failed: int = 0,
        links_discovered: int = 0,
        new_domains_found: int = 0,
    ) -> None:
        """Increment crawl session counters."""
        self.conn.execute(
            "UPDATE crawl_sessions SET pages_crawled = pages_crawled + ?, pages_failed = pages_failed + ?, links_discovered = links_discovered + ?, new_domains_found = new_domains_found + ? WHERE id = ?",
            (pages_crawled, pages_failed, links_discovered, new_domains_found, session_id),
        )
        self.conn.commit()

    def get_page_by_url(self, url: str) -> Optional[sqlite3.Row]:
        """Return a page record by URL."""
        cur = self.conn.execute(
            "SELECT * FROM pages WHERE url = ?",
            (url,),
        )
        return cur.fetchone()
