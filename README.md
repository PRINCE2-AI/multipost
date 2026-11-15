# Automated Multi-Platform Posting System

One `POST /posting` takes a short message with a call-to-action link and publishes it
to six platforms independently, then reports a per-platform result: status, the
published URL, whether that URL is publicly accessible, date, time, and the error if
the platform refused.

Built with FastAPI, Pydantic, HTTPX and Python 3.11. Ships in dry-run mode, so the
whole API is reviewable before a single credential exists.

## Run it

```bash
python -m venv .venv && . .venv/Scripts/activate     # Windows
# source .venv/bin/activate                          # macOS / Linux
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 4000
```

Interactive docs: <http://localhost:4000/docs>

## Test it

```bash
curl -s localhost:4000/posting -H "Content-Type: application/json" -d '{
  "message": "Check out our latest business platform and grow your online visibility. https://example.com"
}'
```

Default output (`DRY_RUN=1`, no credentials needed) — this is an actual response from
the run on this machine:

```json
{
  "success": true,
  "dry_run": true,
  "results": [
    {"platform": "Telegram", "status": "dry_run", "posted_url": null, "public_access": false, "date": null, "time": null, "error": null},
    {"platform": "Mastodon", "status": "dry_run", "posted_url": null, "public_access": false, "date": null, "time": null, "error": null},
    {"platform": "Bluesky",  "status": "dry_run", "posted_url": null, "public_access": false, "date": null, "time": null, "error": null},
    {"platform": "Dev.to",   "status": "dry_run", "posted_url": null, "public_access": false, "date": null, "time": null, "error": null},
    {"platform": "Discord",  "status": "dry_run", "posted_url": null, "public_access": false, "date": null, "time": null, "error": null},
    {"platform": "Slack",    "status": "dry_run", "posted_url": null, "public_access": false, "date": null, "time": null, "error": null}
  ]
}
```

With `DRY_RUN=0` and credentials in place, each entry becomes the real result:

```json
{
  "success": true,
  "dry_run": false,
  "results": [
    {"platform": "Telegram", "status": "success", "posted_url": "https://t.me/my_channel/42",
     "public_access": true, "date": "2026-11-15", "time": "10:30:00", "error": null},
    {"platform": "Mastodon", "status": "failed", "posted_url": null, "public_access": false,
     "date": null, "time": null, "error": "MASTODON_TOKEN is not set"}
  ]
}
```

`success` is `false` only when **every** platform failed; partial results are reported
per platform, which is what the other five entries are for. Times are UTC.

## Validation

| Rule | Behaviour |
| --- | --- |
| Message must not be empty | `422` `{"detail": {"message": "must not be empty"}}` |
| Message must be ≤ 200 characters | `422` with `length` in the detail |
| Exactly one link | `422` with `links_found` |
| Link must be a valid `http(s)` URL with a host | `422` with the offending `link` |

```bash
$ curl -s localhost:4000/posting -H "Content-Type: application/json" \
    -d '{"message":"a https://example.com b https://example.org"}'
{"detail":{"message":"must contain exactly one link","links_found":2}}

$ curl -s localhost:4000/posting -H "Content-Type: application/json" \
    -d '{"message":"click https://localhost"}'
{"detail":{"message":"the link is not a valid http(s) URL","link":"https://localhost"}}
```

Platform selection is internal (`ENABLED_PLATFORMS` in `.env`); the caller only sends
a message, exactly as the brief requires.

## Platforms

| Platform | Official API | Credentials | `posted_url` | `public_access` |
| --- | --- | --- | --- | --- |
| Telegram | [Bot API `sendMessage`](https://core.telegram.org/bots/api#sendmessage) | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | `https://t.me/<channel>/<msg_id>` | `true` only for public channels |
| Mastodon | [`POST /api/v1/statuses`](https://docs.joinmastodon.org/methods/statuses/#create) | `MASTODON_BASE_URL`, `MASTODON_TOKEN` | status URL from the response | `true` when visibility is `public` |
| Bluesky | [AT Protocol `createRecord`](https://docs.bsky.app/docs/advanced-guides/posts) | `BLUESKY_HANDLE`, `BLUESKY_APP_PASSWORD` | `https://bsky.app/profile/<handle>/post/<rkey>` | `true` |
| Dev.to | [Forem API `POST /api/articles`](https://developers.forem.com/api/v1#tag/articles) | `DEVTO_API_KEY` | article URL | `true` when published |
| Discord | [Webhook execute](https://discord.com/developers/docs/resources/webhook#execute-webhook) | `DISCORD_WEBHOOK_URL` | `https://discord.com/channels/<guild>/<channel>/<msg>` | `false` — a webhook can target a private channel |
| Slack | [Incoming webhooks](https://api.slack.com/messaging/webhooks) | `SLACK_WEBHOOK_URL` | `null` — webhooks return no message id | `false` |

The link is turned into a real Bluesky rich-text facet (byte offsets, as the AT
Protocol requires), so it renders as a clickable link rather than plain text. Dev.to
requires a title, so one is derived from the message with the URL removed.

### What I deliberately left out

X/Twitter, LinkedIn, Reddit and Tumblr all need OAuth apps, developer approval or paid
tiers, which a reviewer cannot exercise. The six above authenticate with a token,
app password or webhook URL, so every integration is testable end to end without
waiting on platform approval. `app/platforms/__init__.py` is a registry: adding a
platform is one class with `name` and `async publish(message) -> (url, public)`, plus
one line in the registry and its variables in `.env.example`.

## Design

```
app/
├── main.py                      # POST /posting, /health, /platforms
├── schemas.py                   # request + response models
├── config.py                    # settings from environment
├── validation.py                # 200 chars, exactly one link, URL check
├── platforms/
│   ├── __init__.py              # registry, dry-run stand-ins
│   ├── base.py                  # PlatformError, credential helper
│   ├── telegram.py  mastodon.py  bluesky.py
│   ├── devto.py     discord.py   slack.py
└── services/
    └── posting_service.py       # fan-out and per-platform result mapping
```

**Fan-out, not a loop of awaits.** `asyncio.gather` runs the six integrations
concurrently, so the response takes as long as the slowest platform, not the sum.
Each coroutine converts its own exceptions into a result row, which is why one
failure cannot stop the rest or abort the response.

**Two error classes.** `PlatformError` means "this platform refused", and its message
becomes the `error` field. Anything else is an adapter bug and is still contained, with
the exception type in `error` so it is visible without reading server logs.

**No retries inside the request.** The contract is one synchronous call with a
per-platform result. A retry loop would stretch the request past the caller's timeout
and could publish twice; failures are reported honestly and the caller decides.

**Dry-run by default.** `DRY_RUN=1` swaps each integration for a stand-in that touches
nothing and reports `dry_run`, so the schema, validation and fan-out can be reviewed
and tested without credentials. There is no way to mistake a dry run for a publish:
the response carries `dry_run: true` and no platform claims success.

**Credentials only from the environment.** `.env` is gitignored; `.env.example` holds
blank placeholders and nothing else is committed.

## Tests

```bash
pytest
```

13 tests: the dry-run contract (six platforms, exact field set), 200-character
boundary and over-length rejection, missing/two/invalid links, empty message, one
failing platform leaving the others intact, all platforms failing reporting
`success: false`, an unexpected adapter exception being contained, missing credentials
reported per platform, the health/platforms endpoints, and an unknown platform name
failing at startup. No network, no credentials.

## With more time

- OAuth-based platforms (X, LinkedIn) behind the same registry.
- Retry with idempotency keys for transient 5xx responses, outside the request.
- Persist every result to SQLite so a posting history survives restarts.
- Per-platform formatting: threads for X, tags for Mastodon, a longer body for Dev.to.
