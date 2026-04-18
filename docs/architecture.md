# v0.1 Crawler Architecture

## Overview

This project is a **clear‑web, metadata‑only crawler** designed to be:

- slow
- safe
- SQL‑backed
- modular
- easy to extend

The core idea: the crawler logic is **network‑agnostic**. Only the
transport layer knows how to fetch pages.

## Components

- `main.py`
  - Orchestrates the crawl.
  - Wires together database, queue, fetcher, parser, safety, and transport.

- `database/`
  - `schema.sql`: defines `sites` and `links` tables.
  - `db.py`: wrapper around SQLite for:
    - inserting/updating sites
    - tracking status
    - storing links
    - selecting next unseen URL

- `crawler/`
  - `fetcher.py`: calls the transport to fetch pages, enforces delay and timeout.
  - `parser.py`: extracts `<title>` and `<a href>` links.
  - `queue.py`: simple queue using `sites` table (status NULL = unseen).
  - `safety.py`: basic safety filters and captcha detection.

- `network/`
  - `transport_clearweb.py`: clear‑web HTTP transport using `requests`.
  - `transport_darkweb.py`: dark-web HTTP transport using Tor SOCKS5.

- `docs/`
  - `architecture.md`: this file.
  - `safety_model.md`: describes safety assumptions and limits.
  - `how_to_extend.md`: explains how to extend or modify the crawler.

## Data Flow

1. `main.py` seeds initial URLs into the queue.
2. `UrlQueue` asks `Database` for the next unseen URL.
3. `Fetcher` uses `ClearWebTransport` to fetch the page.
4. `Safety` checks:
   - HTML sanity
   - captcha detection
5. `Parser` extracts:
   - title
   - links
6. `Database`:
   - updates site status and title
   - ensures linked sites exist
   - stores link relationships
7. New URLs are added back into the queue.

## Network Abstraction

The crawler never calls `requests` directly.

It only calls:

```python
response = transport.get(url, timeout=...)
