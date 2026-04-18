
---

### `docs/safety_model.md`

```markdown
# Safety Model (v0.1)

## Goals

- Metadata‑only crawling.
- No interaction with forms, logins, or dynamic content.
- No execution of JavaScript.
- No downloading of files.
- No solving of captchas.

## What the crawler does

- Fetches pages as plain text.
- Extracts:
  - HTTP status (indirectly via success/failure).
  - `<title>` text.
  - `<a href>` links.
- Stores:
  - URL
  - status (`working`, `dead`, `captcha`, `timeout`)
  - title
  - link relationships

## What the crawler does NOT do

- Does not render pages.
- Does not execute JavaScript.
- Does not download binary files.
- Does not submit forms.
- Does not log in.
- Does not attempt to solve captchas.
- Does not parse or act on user‑generated content.

## Captcha Handling

If the HTML contains common captcha phrases (e.g. "captcha",
"are you a robot", "verify you are human", "cloudflare", "challenge"),
the page is marked as `captcha` and not processed further.

## Limitations

This is a **simple v0.1 model**. It is not a full security system.
You can expand `Safety` with:

- more robust content checks
- domain allow/deny lists
- stricter URL validation
- rate limiting per domain
