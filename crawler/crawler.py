import hashlib
import logging
from typing import List, Optional, Tuple

from crawler.fetcher import Fetcher
from crawler.parser import Parser
from crawler.queue import UrlQueue
from crawler.safety import RobotsChecker, Safety
from database.db import Database
from network.transport_clearweb import ClearWebTransport
from network.transport_darkweb import DarkWebTransport


class Crawler:
    """Coordinates page discovery, crawling, and database updates."""

    def __init__(
        self,
        db: Database,
        transport: object,
        max_depth: int = 3,
        max_pages: int = 1000,
        domain_scope: Optional[str] = None,
        delay_seconds: float = 2.0,
        respect_robots: Optional[bool] = None,
    ) -> None:
        self.logger = logging.getLogger(__name__)
        self.db = db
        self.transport = transport
        self.fetcher = Fetcher(transport, delay_seconds=delay_seconds)
        self.parser = Parser()
        self.safety = Safety()
        self.queue = UrlQueue(db)
        self.max_depth = max_depth
        self.max_pages = max_pages
        self.delay_seconds = delay_seconds
        self.domain_scope = domain_scope or self._default_scope()
        self.respect_robots = (
            respect_robots
            if respect_robots is not None
            else self._default_respect_robots()
        )
        self.robots_checker = (
            RobotsChecker(transport) if self.respect_robots else None
        )
        self.session_id: Optional[int] = None
        self.pages_fetched = 0

    def _default_scope(self) -> str:
        if isinstance(self.transport, DarkWebTransport):
            return "onion_only"
        if isinstance(self.transport, ClearWebTransport):
            return "clearweb_only"
        return "any"

    def _default_respect_robots(self) -> bool:
        return not isinstance(self.transport, DarkWebTransport)

    def _is_allowed_by_scope(self, url: str) -> Tuple[bool, str]:
        from urllib.parse import urlparse

        domain = urlparse(url).netloc.lower()
        if self.domain_scope == "onion_only" and not domain.endswith(".onion"):
            return False, "scope violation: clearweb URL in onion_only mode"
        if self.domain_scope == "clearweb_only" and domain.endswith(".onion"):
            return False, "scope violation: onion URL in clearweb_only mode"
        return True, ""

    def _hash_body(self, body: str) -> str:
        return hashlib.sha256(body.encode("utf-8", errors="ignore")).hexdigest()

    def _record_session_stats(
        self,
        pages_crawled: int = 0,
        pages_failed: int = 0,
        links_discovered: int = 0,
        new_domains_found: int = 0,
    ) -> None:
        if self.session_id is None:
            return
        self.db.increment_crawl_session_stats(
            self.session_id,
            pages_crawled=pages_crawled,
            pages_failed=pages_failed,
            links_discovered=links_discovered,
            new_domains_found=new_domains_found,
        )

    def crawl(self, seed_urls: List[str]) -> None:
        """Run the crawl session over the provided seed URLs."""
        transport_type = (
            "tor" if isinstance(self.transport, DarkWebTransport) else "clearweb"
        )
        self.session_id = self.db.start_crawl_session(
            transport_type=transport_type,
            seed_urls=seed_urls,
            max_depth=self.max_depth,
            max_pages=self.max_pages,
        )
        self.logger.info(
            "Starting crawl session %s with max_depth=%s max_pages=%s domain_scope=%s respect_robots=%s",
            self.session_id,
            self.max_depth,
            self.max_pages,
            self.domain_scope,
            self.respect_robots,
        )

        for seed in seed_urls:
            allowed, reason = self._is_allowed_by_scope(seed)
            if not allowed:
                self.logger.warning("Seed skipped: %s (%s)", seed, reason)
                continue
            if not self.safety.is_potentially_valid_url(seed):
                self.logger.warning("Seed skipped: invalid URL %s", seed)
                continue
            page_id, created_domain = self.db.insert_page(
                seed,
                crawl_depth=0,
                session_id=self.session_id,
            )
            if created_domain:
                self._record_session_stats(new_domains_found=1)

        while self.pages_fetched < self.max_pages:
            next_pages = self.db.get_next_uncrawled(limit=1)
            if not next_pages:
                self.logger.info("No more pending pages to crawl.")
                break
            page_id, url, depth = next_pages[0]
            if depth > self.max_depth:
                self.logger.info(
                    "Skipping %s because it exceeds max_depth=%s",
                    url,
                    self.max_depth,
                )
                self.db.update_page_status(page_id, status="failed")
                self._record_session_stats(pages_failed=1)
                continue

            if self.respect_robots and self.robots_checker is not None:
                if not self.robots_checker.is_allowed(url):
                    self.logger.info("Robots blocked: %s", url)
                    self.db.update_page_status(page_id, status="robots_blocked")
                    self._record_session_stats(pages_failed=1)
                    continue

            html, status_code, error, response = self.fetcher.fetch(url)
            if error is not None or response is None:
                self.logger.warning("Fetch failed for %s: %s", url, error)
                self.db.update_page_status(
                    page_id,
                    status="timeout",
                    http_code=status_code,
                )
                self._record_session_stats(pages_failed=1)
                self.pages_fetched += 1
                if self.pages_fetched >= self.max_pages:
                    self.logger.info(
                        "Max pages reached (%s). Stopping crawl.",
                        self.max_pages,
                    )
                continue

            if not self.safety.is_safe_html(html):
                self.logger.warning("Unsafe HTML detected: %s", url)
                self.db.update_page_status(
                    page_id,
                    status="failed",
                    http_code=status_code,
                )
                self._record_session_stats(pages_failed=1)
                self.pages_fetched += 1
                continue

            if self.safety.is_captcha_page(html):
                self.logger.info("Captcha page detected: %s", url)
                self.db.update_page_status(
                    page_id,
                    status="captcha",
                    http_code=status_code,
                )
                self._record_session_stats(pages_failed=1)
                self.pages_fetched += 1
                continue

            title = self.parser.extract_title(html)
            content_hash = self._hash_body(html)
            server_header = (
                response.headers.get("Server") if response is not None else None
            )
            page_size = len(html.encode("utf-8"))
            self.db.update_page_status(
                page_id,
                status="crawled",
                http_code=status_code,
                content_hash=content_hash,
                page_size=page_size,
                server_header=server_header,
                title=title,
            )
            self.pages_fetched += 1
            self._record_session_stats(pages_crawled=1)

            links = self.parser.extract_links(html, base_url=url)
            discovered_count = 0
            new_domain_count = 0
            for discovered_url, anchor_text in links:
                if not self.safety.is_potentially_valid_url(discovered_url):
                    continue
                allowed, reason = self._is_allowed_by_scope(discovered_url)
                if not allowed:
                    self.logger.info("Discarded URL %s: %s", discovered_url, reason)
                    continue
                child_id, created_domain = self.db.insert_page(
                    discovered_url,
                    crawl_depth=depth + 1,
                    session_id=self.session_id,
                )
                if created_domain:
                    new_domain_count += 1
                self.db.insert_link(
                    from_page_id=page_id,
                    to_page_id=child_id,
                    anchor_text=anchor_text,
                    session_id=self.session_id,
                )
                discovered_count += 1

            self._record_session_stats(
                links_discovered=discovered_count,
                new_domains_found=new_domain_count,
            )

            if self.pages_fetched >= self.max_pages:
                self.logger.info(
                    "Max pages reached (%s). Stopping crawl.",
                    self.max_pages,
                )
                break

        if self.session_id is not None:
            self.db.end_crawl_session(
                self.session_id,
                status="completed",
            )
            self.logger.info("Crawl session %s completed.", self.session_id)
