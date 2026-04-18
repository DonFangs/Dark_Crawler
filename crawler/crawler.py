import hashlib
import logging
import threading
import time
from datetime import datetime, UTC
from typing import Dict, List, Optional
from urllib.parse import urlparse

from crawler.fetcher import Fetcher
from crawler.parser import Parser, normalize_url
from crawler.queue import UrlQueue
from crawler.safety import RobotsChecker, Safety
from database.db import Database
from network.transport_darkweb import DarkWebTransport


class Crawler:
    """Tor-only crawler for discovering .onion network structure.
    
    Maintains a graph of domains, pages, and links discovered through
    automated crawling starting from seed URLs.
    """

    def __init__(
        self,
        db: Database,
        transport: DarkWebTransport,
        max_depth: int = 3,
        max_pages: int = 1000,
        delay_seconds: float = 2.0,
        respect_robots: bool = False,
        shutdown_event: Optional[threading.Event] = None,
    ) -> None:
        """Initialize the crawler.
        
        Args:
            db: Database instance.
            transport: DarkWebTransport instance for Tor access.
            max_depth: Maximum crawl depth (default: 3).
            max_pages: Maximum pages to fetch (default: 1000).
            delay_seconds: Delay between requests per domain (default: 2.0).
            respect_robots: Whether to check robots.txt (default: False).
            shutdown_event: Threading event for graceful shutdown (optional).
        """
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
        self.respect_robots = respect_robots
        self.robots_checker = RobotsChecker(transport) if self.respect_robots else None
        self.shutdown_event = shutdown_event or threading.Event()
        self.session_id: Optional[int] = None
        self.pages_fetched = 0
        self.domain_last_fetch: Dict[str, float] = {}

    def _is_onion_url(self, url: str) -> bool:
        """Check if URL is a .onion domain.
        
        Args:
            url: URL to check.
            
        Returns:
            True if domain ends with .onion.
        """
        domain = urlparse(url).netloc.lower()
        return domain.endswith(".onion")

    def _apply_domain_rate_limit(self, url: str) -> None:
        """Apply per-domain rate limiting before fetching.
        
        Args:
            url: URL about to be fetched.
        """
        domain = urlparse(url).netloc.lower()
        now = time.time()
        last_fetch = self.domain_last_fetch.get(domain, 0)
        elapsed = now - last_fetch
        if elapsed < self.delay_seconds:
            wait_time = self.delay_seconds - elapsed
            self.logger.debug("Rate limiting %s: waiting %.2f seconds", domain, wait_time)
            time.sleep(wait_time)
        self.domain_last_fetch[domain] = time.time()

    def _hash_body(self, body: str) -> str:
        """Compute SHA-256 hash of page body.
        
        Args:
            body: HTML body content.
            
        Returns:
            Hex-encoded SHA-256 hash.
        """
        return hashlib.sha256(body.encode("utf-8", errors="ignore")).hexdigest()

    def _record_session_stats(
        self,
        pages_crawled: int = 0,
        pages_failed: int = 0,
        links_discovered: int = 0,
        new_domains_found: int = 0,
    ) -> None:
        """Update session statistics.
        
        Args:
            pages_crawled: Pages successfully crawled.
            pages_failed: Pages that failed.
            links_discovered: Links found.
            new_domains_found: New domains discovered.
        """
        if self.session_id is None:
            return
        self.db.increment_crawl_session_stats(
            self.session_id,
            pages_crawled=pages_crawled,
            pages_failed=pages_failed,
            links_discovered=links_discovered,
            new_domains_found=new_domains_found,
        )

    def crawl(self, seed_urls: List[str]) -> Optional[int]:
        """Run the crawl session over the provided seed URLs.
        
        Args:
            seed_urls: List of .onion seed URLs to start crawling from.
            
        Returns:
            Session ID of the completed crawl, or None if failed.
        """
        self.session_id = self.db.start_crawl_session(
            transport_type="tor",
            seed_urls=seed_urls,
            max_depth=self.max_depth,
            max_pages=self.max_pages,
        )
        self.logger.info(
            "Starting crawl session %s with max_depth=%s max_pages=%s respect_robots=%s",
            self.session_id,
            self.max_depth,
            self.max_pages,
            self.respect_robots,
        )

        for seed in seed_urls:
            if self.shutdown_event.is_set():
                self.logger.info("Shutdown requested during seed processing, stopping.")
                break
                
            if not self._is_onion_url(seed):
                self.logger.warning("Seed skipped: not a .onion URL: %s", seed)
                continue
            if not self.safety.is_potentially_valid_url(seed):
                self.logger.warning("Seed skipped: invalid URL %s", seed)
                continue
            seed_normalized = normalize_url(seed)
            page_id, created_domain = self.db.insert_page(
                seed_normalized,
                crawl_depth=0,
                session_id=self.session_id,
            )
            if created_domain:
                self._record_session_stats(new_domains_found=1)

        while self.pages_fetched < self.max_pages:
            if self.shutdown_event.is_set():
                self.logger.info("Shutdown requested, finishing current page...")
                break

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

            if not self._is_onion_url(url):
                self.logger.warning("Scope violation: skipping non-.onion URL %s", url)
                self.db.update_page_status(page_id, status="failed")
                self._record_session_stats(pages_failed=1)
                continue

            if self.respect_robots and self.robots_checker is not None:
                if not self.robots_checker.is_allowed(url):
                    self.logger.info("Robots blocked: %s", url)
                    self.db.update_page_status(page_id, status="robots_blocked")
                    self._record_session_stats(pages_failed=1)
                    continue

            self._apply_domain_rate_limit(url)

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
                    final_url=response.url if response else None,
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
                    final_url=response.url if response else None,
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
            final_url = response.url if response else url
            
            self.db.update_page_status(
                page_id,
                status="crawled",
                http_code=status_code,
                content_hash=content_hash,
                page_size=page_size,
                server_header=server_header,
                title=title,
                final_url=final_url,
            )
            self.pages_fetched += 1
            self._record_session_stats(pages_crawled=1)

            links = self.parser.extract_links(html, base_url=url)
            discovered_count = 0
            new_domain_count = 0
            for discovered_url, anchor_text in links:
                if not self.safety.is_potentially_valid_url(discovered_url):
                    continue
                    
                if not self._is_onion_url(discovered_url):
                    self.logger.debug("Skipped non-.onion URL: %s", discovered_url)
                    continue
                    
                discovered_normalized = normalize_url(discovered_url)
                child_id, created_domain = self.db.insert_page(
                    discovered_normalized,
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
                    discovered_at_depth=depth,
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
            status = "stopped" if self.shutdown_event.is_set() else "completed"
            self.db.end_crawl_session(self.session_id, status=status)
            self.logger.info("Crawl session %s %s.", self.session_id, status)

        return self.session_id
