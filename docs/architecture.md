# Dark Crawler Architecture

## Overview

This project is a **Tor-only, metadata-only crawler** for .onion networks.

Design principles:
- **Tor-exclusive**: All access through .onion addresses only
- **Metadata focus**: Stores links, titles, and domain graph (no content)
- **Rate-limited**: Per-domain delays to avoid server overload
- **Safe**: CAPTCHA detection, HTML sanity checks, graceful shutdown
- **SQL-backed**: SQLite3 with Write-Ahead Logging for concurrent access
- **Modular**: Transport layer abstraction, reusable components

## Components

- `main.py`
  - CLI entry point with seed URL loading
  - Verifies Tor connectivity at startup
  - Sets up signal handlers for graceful shutdown
  - Logs session summary with statistics

- `database/`
  - `schema.sql`: Domain/page/link graph with session tracking
  - `db.py`: SQLite abstraction with WAL mode and parameterized queries
  - `db_manager.py`: Session management and statistics

- `crawler/`
  - `fetcher.py`: HTTP requests via transport with retry logic
  - `parser.py`: HTML link extraction with URL normalization
  - `queue.py`: Breadth-first queue using database
  - `safety.py`: HTML sanity, CAPTCHA detection, content type filtering
  - `crawler.py`: Main crawl coordinator with .onion filtering and rate limiting

- `network/`
  - `transport_darkweb.py`: Tor SOCKS5 transport with Content-Type guards

- `docs/`
  - `architecture.md`: this file
  - `safety_model.md`: Security assumptions and threat model
  - `how_to_extend.md`: Extension guide

## Data Flow

1. `main.py` verifies Tor connectivity via check.torproject.org
2. Seed .onion URLs loaded and validated (must be .onion domain)
3. `Crawler.crawl()` creates crawl session in database
4. Main loop:
   - Check for shutdown signal
   - Get next uncrawled URL from queue
   - Apply per-domain rate limit
   - `Fetcher` retrieves page via Tor SOCKS5
   - Verify Content-Type is HTML/text
   - Track redirects and final URL
   - `Safety` sanity checks (HTML, CAPTCHA detection)
   - `Parser` extracts links with normalization (fragments removed, params sorted, lowercased)
   - Filter discovered links: must be .onion addresses
   - Update database with page metadata and links
5. On shutdown signal or max pages reached: end session, log summary

## URL Normalization

All URLs normalized for deduplication:
- Fragments (#) removed
- Trailing slashes removed (except root /)
- Scheme and netloc lowercased
- Query parameters sorted alphabetically
- Ensures same logical URL always has same storage key

## Network Abstraction

The crawler never calls `requests` directly.

It only calls:

```python
response = transport.get(url, timeout=...)
