# Dark Crawler

A passive metadata-only crawler for mapping link relationships across clearweb and .onion domains.

## Description

Dark Crawler is designed to discover page-level relationships without storing page content. It builds a graph of domains, pages, and links while respecting safe crawl boundaries, robots.txt policies, and Tor connectivity for onion crawling.

## Installation

1. Create a Python virtual environment.
2. Install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

## Usage

### Clearweb mode

```bash
python main.py --transport clearweb --seeds seeds_clearweb.txt --max-depth 3 --max-pages 1000 --delay 2.0 --db-path dark_crawler.db
```

### Tor mode

```bash
python main.py --transport tor --seeds seeds_onion.txt --max-depth 3 --max-pages 1000 --delay 2.0 --db-path dark_crawler.db
```

### Logging

You can write logs to a file:

```bash
python main.py --log-file crawler.log --log-level DEBUG
```

## Database schema

The crawler stores the graph using:

- `domains`: unique domains, onion metadata, status, and discovery timestamps
- `pages`: full URLs, HTTP metadata, crawl depth, and crawl history
- `links`: directed edges between pages with anchor text and discovery time
- `crawl_sessions`: session metadata and counters for each run

Views are also created for graph analysis such as `domain_in_degree`, `domain_out_degree`, `hub_domains`, `isolated_domains`, and `domain_graph_edges`.

## Safety features

- Domain scope filtering: `onion_only`, `clearweb_only`, or `any`
- Optional robots.txt checking with `--respect-robots`
- CAPTCHA detection using structural HTML analysis
- Tor connectivity verification before darkweb crawling
- Retry with exponential backoff for transport failures

## Disclaimer

This project is for educational and research purposes only. Use it responsibly and always respect site policies and legal restrictions.
