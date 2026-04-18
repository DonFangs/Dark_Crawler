# How to Extend the Crawler

## 1. Add more page statuses

Currently tracked statuses:

- `uncrawled`: Initial state (NULL in older code)
- `crawled`: Successfully fetched and parsed
- `failed`: Fetch or safety check failed
- `timeout`: Connection timeout
- `captcha`: CAPTCHA detected
- `robots_blocked`: Rejected by robots.txt

To add more:

1. Update `database/schema.sql` (pages table CHECK constraint)
2. Update `database/db.py` docstrings
3. Update `crawler/crawler.py` where status is set

## 2. Enhance safety filters

Edit `crawler/safety.py`:

- Add more CAPTCHA keywords or regex patterns
- Add HTML patterns for disallowed content
- Add domain-specific allow/deny lists
- Add fingerprinting detection

## 3. Improve URL parsing

Edit `crawler/parser.py`:

- Extend `normalize_url()` for more edge cases
- Add URL filtering (e.g., block tracking parameters)
- Add subdomain extraction for analysis
- Add javascript: or data: URI filtering

## 4. Customize Tor transport

Edit `network/transport_darkweb.py`:

- Adjust retry backoff timing (currently 2s, 4s, 8s)
- Add proxy rotation if multiple Tor instances available
- Add HTTP header customization
- Add Connection pool tuning for performance

## 5. Add database indexes or views

Edit `database/schema.sql`:

- Add new indexes for frequent queries
- Create new views for analysis (e.g., crawl depth distribution)
- Add constraints for data integrity

## 6. Extend rate limiting

Currently per-domain rate limiting is configured by `--delay` flag.

To add more sophisticated limiting:

1. Modify `_apply_domain_rate_limit()` in `crawler/crawler.py`
2. Add global rate limiting (e.g., max concurrent requests)
3. Add adaptive rate limiting (detect 429 responses, back off)
4. Track per-IP limits if you resolve IPs

## 7. Add metrics or analytics

Extend `crawler.py` and `main.py` to track:

- Crawl speed over time
- Error rate by domain
- Link depth distribution
- Domain graph properties (clustering, centrality)
- .onion version distribution

Store in database or export to logs/metrics files.