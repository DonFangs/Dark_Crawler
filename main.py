from crawler.logger import setup_logging

import argparse
import logging
import signal
import sys
import threading
from datetime import datetime, UTC
from pathlib import Path
from typing import List, Optional

from crawler.crawler import Crawler
from database.db import Database
from network.transport_darkweb import DarkWebTransport


def load_seed_urls(path: str) -> List[str]:
    """Load seed URLs from a file, ignoring comments and blank lines.
    
    Args:
        path: Path to seed file.
        
    Returns:
        List of seed URLs.
        
    Raises:
        FileNotFoundError: If seed file does not exist.
        ValueError: If any seed URL is invalid.
    """
    seeds_path = Path(path)
    if not seeds_path.exists():
        raise FileNotFoundError(f"Seed file not found: {path}")

    urls = [
        line.strip()
        for line in seeds_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    
    from urllib.parse import urlparse
    import logging
    logger = logging.getLogger(__name__)
    
    valid_urls = []
    for url in urls:
        try:
            parsed = urlparse(url)
            netloc = parsed.netloc.lower()
            if not netloc.endswith('.onion'):
                logger.warning("Seed URL rejected: netloc does not end with .onion: %s", url)
                continue
            if parsed.scheme not in ('http', 'https'):
                logger.warning("Seed URL rejected: invalid scheme (must be http or https): %s", url)
                continue
            valid_urls.append(url)
        except Exception as exc:
            logger.warning("Seed URL rejected: parsing failed for %s: %s", url, exc)
            continue
    
    if not valid_urls:
        raise ValueError(f"No valid .onion URLs found in {path}")
    
    return valid_urls


def parse_args() -> argparse.ArgumentParser:
    """Parse command-line arguments.
    
    Returns:
        Configured argument parser.
    """
    parser = argparse.ArgumentParser(
        description="Dark Crawler v0.2: Tor-only passive metadata crawler for .onion link mapping"
    )
    parser.add_argument(
        "--seeds",
        required=True,
        help="Path to a text file containing one .onion seed URL per line",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=3,
        help="Maximum crawl depth (default: 3)",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=1000,
        help="Maximum number of pages to fetch (default: 1000)",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Seconds to wait between requests (default: 2.0)",
    )
    parser.add_argument(
        "--db-path",
        default="dark_crawler.db",
        help="SQLite database file path (default: dark_crawler.db)",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)",
    )
    parser.add_argument(
        "--log-file",
        help="Optional path to write log output",
    )
    parser.add_argument(
        "--respect-robots",
        action="store_true",
        default=False,
        help="Respect robots.txt when crawling (default: False, as .onion sites rarely have it)",
    )
    return parser


def main() -> None:
    """Main entry point for the crawler."""
    parser = parse_args()
    args = parser.parse_args()

    setup_logging(args.log_level, args.log_file)
    logger = logging.getLogger(__name__)

    try:
        seed_urls = load_seed_urls(args.seeds)
    except (FileNotFoundError, ValueError) as exc:
        logger.error(str(exc))
        sys.exit(1)
    
    if not seed_urls:
        logger.error("No seed URLs loaded from %s", args.seeds)
        sys.exit(1)

    logger.info("Loaded %d seed URLs from %s", len(seed_urls), args.seeds)

    db = Database(args.db_path)
    db.init_schema()

    transport = DarkWebTransport()
    
    shutdown_event = threading.Event()
    
    def signal_handler(signum: int, frame: object) -> None:
        """Handle SIGINT and SIGTERM for graceful shutdown."""
        logger.info("Shutdown signal received (signal %d), finishing current page...", signum)
        shutdown_event.set()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    crawler = Crawler(
        db=db,
        transport=transport,
        max_depth=args.max_depth,
        max_pages=args.max_pages,
        delay_seconds=args.delay,
        respect_robots=args.respect_robots,
        shutdown_event=shutdown_event,
    )
    
    start_time = datetime.now(UTC)
    session_id = crawler.crawl(seed_urls)
    end_time = datetime.now(UTC)
    
    if session_id is not None:
        duration = end_time - start_time
        minutes = int(duration.total_seconds() // 60)
        seconds = int(duration.total_seconds() % 60)
        
        try:
            session_stats = db.get_crawl_session_stats(session_id)
            domain_stats = db.get_domain_stats()
            import os
            db_size_mb = os.path.getsize(args.db_path) / (1024 * 1024)
        except Exception:
            session_stats = {}
            domain_stats = {}
            db_size_mb = 0.0
        
        logger.info(
            "\n===== CRAWL SESSION COMPLETE =====\n"
            "Session ID: %s\n"
            "Duration: %dm %ds\n"
            "Pages crawled: %d\n"
            "Pages failed: %d\n"
            "Links discovered: %d\n"
            "New domains found: %d\n"
            "Database size: %.2f MB\n"
            "==================================",
            session_id,
            minutes,
            seconds,
            session_stats.get("pages_crawled", 0),
            session_stats.get("pages_failed", 0),
            session_stats.get("links_discovered", 0),
            session_stats.get("new_domains_found", 0),
            db_size_mb,
        )


if __name__ == "__main__":
    main()
