# Dark Crawler

A Tor-only passive metadata crawler for mapping .onion network topology and link relationships.

## Description

Dark Crawler discovers .onion sites and builds a graph of domains, pages, and links without storing page content. It operates exclusively through Tor, automatically following links across the darkweb starting from seed URLs.

## Installation

1. Ensure Tor is running on `127.0.0.1:9050` (SOCKS5 proxy)
2. Create a Python virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

## Usage

Start a crawl with seed URLs:

```bash
python main.py --seeds seeds_onion.txt --max-depth 3 --max-pages 1000 --delay 2.0
```

### Available Options

- `--seeds FILE` (required): Path to text file with .onion seed URLs
- `--max-depth N` (default: 3): Maximum crawl depth
- `--max-pages N` (default: 1000): Maximum pages to fetch
- `--delay SECONDS` (default: 2.0): Per-domain rate limit
- `--db-path PATH` (default: dark_crawler.db): SQLite database file
- `--log-level LEVEL` (default: INFO): DEBUG, INFO, WARNING, or ERROR
- `--log-file PATH` (optional): Write logs to file
- `--respect-robots` (default: False): Check robots.txt before crawling

### Example: Crawl with logging

```bash
python main.py --seeds seeds_onion.txt --max-pages 500 --log-file crawler.log --log-level DEBUG
```

Graceful shutdown: Press `Ctrl+C` to finish the current page and exit cleanly.

## Database Schema

The crawler stores the graph using:

- `domains`: unique .onion domains with version detection, status, and timestamps
- `pages`: full URLs, HTTP metadata, content hash, crawl depth, and redirect tracking
- `links`: directed edges with anchor text and discovery depth
- `crawl_sessions`: session metadata and statistics for each run

Includes indexes for efficient graph queries and views for analyzing domain connectivity.

## Safety Features

- Tor connectivity verification before crawling
- .onion-only filtering (no clearweb leakage)
- CAPTCHA detection using structural HTML analysis
- Optional robots.txt checking (default: disabled for .onion)
- Per-domain rate limiting to avoid server overload
- Graceful shutdown on interrupt signals
- Retry logic with exponential backoff on failures
- Content-Type filtering (HTML/text only)
- Redirect tracking and final URL recording

## Disclaimer

This project is for educational and research purposes only. Unauthorized access to computer networks is illegal. Always ensure you have proper authorization and respect site policies, legal restrictions, and the terms of service.

