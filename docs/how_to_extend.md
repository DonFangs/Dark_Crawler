# How to Extend the v0.1 Crawler

## 1. Add more statuses

Currently used statuses:

- `working`
- `dead`
- `captcha`
- `timeout` (not yet explicitly set, but reserved)
- `NULL` = unseen

You can add more, e.g.:

- `blocked`
- `redirect_loop`
- `unsupported`

Update:

- `database/schema.sql`
- `database/db.py`
- any logic in `main.py` that sets status.

## 2. Improve safety filters

Edit `crawler/safety.py`:

- Add more keywords for captchas.
- Add checks for disallowed content patterns.
- Add domain allow/deny lists.
- Add per‑domain rate limiting (you can track last access times in the DB).

## 3. Improve parsing

Edit `crawler/parser.py`:

- Handle more HTML edge cases.
- Normalize URLs more aggressively.
- Filter out tracking or junk URLs.

## 4. Swap or extend the transport

The crawler uses a **transport abstraction**:

- Implemented in `network/transport_clearweb.py`.
- Implemented in `network/transport_darkweb.py`.

The fetcher only calls:

```python
response = transport.get(url, timeout=...)
