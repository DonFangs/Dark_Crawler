from crawler.logger import setup_logging

import argparse
import logging
from pathlib import Path
from typing import List, Optional

from crawler.crawler import Crawler
from database.db import Database
from network.transport_clearweb import ClearWebTransport
from network.transport_darkweb import DarkWebTransport


def load_seed_urls(path: Optional[str]) -> List[str]:
    """Load seed URLs from a file, ignoring comments and blank lines."""
    if not path:
        return []
    seeds_path = Path(path)
    if not seeds_path.exists():
        raise FileNotFoundError(f"Seed file not found: {path}")

    with seeds_path.open("r", encoding="utf-8") as handle:
        return [
            line.strip()
            for line in handle
            if line.strip() and not line.strip().startswith("#")
        ]


def parse_args() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Dark Crawler v0.2: passive metadata-only crawler for link mapping"
    )
    parser.add_argument(
        "--transport",
        choices=["tor", "clearweb"],
        default="clearweb",
        help="Transport mode for crawling",
    )
    parser.add_argument(
        "--seeds",
        help="Path to a text file containing one seed URL per line",
    )
    parser.add_argument(
        "--max-depth",
        type=int,
        default=3,
        help="Maximum crawl depth",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=1000,
        help="Maximum number of pages to fetch",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Seconds to wait between requests",
    )
    parser.add_argument(
        "--db-path",
        default="dark_crawler.db",
        help="SQLite database file path",
    )
    parser.add_argument(
        "--domain-scope",
        choices=["onion_only", "clearweb_only", "any"],
        help="Domain scope filter for discovered URLs",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level",
    )
    parser.add_argument(
        "--log-file",
        help="Optional path to write log output",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--respect-robots",
        dest="respect_robots",
        action="store_true",
        help="Respect robots.txt when crawling",
    )
    group.add_argument(
        "--no-respect-robots",
        dest="respect_robots",
        action="store_false",
        help="Ignore robots.txt when crawling",
    )
    parser.set_defaults(respect_robots=None)
    return parser


def main() -> None:
    parser = parse_args()
    args = parser.parse_args()

    setup_logging(args.log_level, args.log_file)
    logger = logging.getLogger(__name__)

    if args.transport == "tor" and not args.seeds:
        parser.error(
            "You must provide a seeds file with .onion URLs when using Tor transport. Example: --seeds my_seeds.txt"
        )

    try:
        seed_urls = load_seed_urls(args.seeds)
    except FileNotFoundError as exc:
        parser.error(str(exc))
        return

    domain_scope = args.domain_scope
    if domain_scope is None:
        domain_scope = "onion_only" if args.transport == "tor" else "clearweb_only"

    respect_robots = args.respect_robots
    if respect_robots is None:
        respect_robots = args.transport == "clearweb"

    db = Database(args.db_path)
    db.init_schema()

    transport = (
        DarkWebTransport() if args.transport == "tor" else ClearWebTransport()
    )

    crawler = Crawler(
        db=db,
        transport=transport,
        max_depth=args.max_depth,
        max_pages=args.max_pages,
        domain_scope=domain_scope,
        delay_seconds=args.delay,
        respect_robots=respect_robots,
    )
    crawler.crawl(seed_urls)


if __name__ == "__main__":
    main()
