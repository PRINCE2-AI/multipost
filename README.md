# Multi-Platform Posting System

Write a post once, deliver it to several platforms independently, retry only the
deliveries that failed, and do not publish twice when a request is retried or two
worker ticks overlap.

FastAPI + SQLite, no external services required to run it. `DRY_RUN=1` is the
default, so the whole pipeline is reviewable without a single API key.

## Quickstart (no credentials)

```bash
python -m venv .venv && . .venv/Scripts/activate    # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload
```

```bash
curl -s localhost:8000/posts -H "Content-Type: application/json" \
  -H "Idempotency-Key: launch-post-1" \
  -d '{"content":"Shipping the posting service today.","platforms":["telegram","mastodon"]}'

curl -s -X POST localhost:8000/tick        # drive the worker now (a background loop also runs)
curl -s localhost:8000/posts/<id>          # status: posted, per platform
cat var/mock_outbox.jsonl                  # what would have been published
```

With `DRY_RUN=1` the scheduler delivers to an outbox file, so the response shape,
retry behaviour and status transitions are all exercised end to end. Set
`SCHEDULER_ENABLED=0` if you would rather step it with `/tick` only.

Live mode: copy `.env.example` to `.env`, set `DRY_RUN=0` and the credentials for
the platforms you want. Telegram is a bot token + chat id, Mastodon a base URL +
token, Dev.to an API key (Dev.to also requires a `title`).

## Architecture

```
POST /posts ──► posts table
                 │
                 └─► attempts table (one row per post × platform, status=pending)
                          │
 scheduler (asyncio) ─────┘  every SCHEDULER_INTERVAL seconds:
   select due attempts → claim (pending→sending) → adapter.send() → posted
                                                                    └─► on error: attempts+1,
                                                                        next_attempt_at = now + backoff,
                                                                        back to pending
                                                     give up after MAX_ATTEMPTS
```

Each platform is an independent row, so a Telegram outage cannot block Mastodon,
and a failure is retried on its own schedule instead of re-publishing the ones
that already succeeded.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/posts` | Queue a post (optional `Idempotency-Key` header) |
| `GET` | `/posts` | List recent posts |
| `GET` | `/posts/{id}` | One post with per-platform attempts |
| `POST` | `/posts/{id}/retry` | Reset failed deliveries to pending |
| `POST` | `/tick` | Run the worker once (deterministic, used by tests) |
| `GET` | `/health` | DB check + dry-run flag + queue depth |
| `GET` | `/platforms` | Supported names and per-platform limits |

Status values: `scheduled` → `partial` → `posted` / `failed`. An attempt is also
briefly `sending` while a worker owns it; that state is internal and never
returned as a post status.

## Design decisions

**One attempts row per platform.** A single `status` column on the post forces
you to either re-send everything or track state in prose. Per-platform rows make
retry, backoff and partial success explicit, and give the reviewer a table that
explains what happened without reading logs.

**Idempotency at the API boundary.** Mobile clients and retries from a load
balancer both duplicate requests. A unique `idempotency_key` is inserted inside
the same transaction as the post, and a duplicate key returns the original post
instead of publishing twice — including when two requests race, where the loser
catches the unique-constraint violation and re-reads the winner.

**Claim before send.** A tick first flips a due row from `pending` to `sending`
with a conditional `UPDATE ... WHERE status = 'pending'`, and only the worker
that changed one row sends it. The scheduler and `POST /tick` can therefore
overlap without double-publishing. A row still `sending` after five minutes is
assumed to belong to a dead process and is returned to the queue — that case is
at-least-once, which is the honest trade-off versus a permanently stuck delivery.

**Exponential backoff with server-provided hints.** `2^n` seconds capped at 300,
but `Retry-After` / Telegram's `parameters.retry_after` win when present — the
platform knows better than a generic curve. Non-retryable errors (bad token,
missing title) fail on the first attempt instead of burning five.

**Validation before the queue, per platform.** Mastodon is 500 characters,
Telegram 4096, Dev.to a long-form article. A post that exceeds the limit of any
requested platform is rejected with a 422 naming the platform and the limit, so
the failure happens at write time rather than at 2 a.m. in the scheduler.

**`/tick` next to the scheduler.** The background loop is the production path, but
exposing one tick makes the worker testable without `sleep()` — the tests move
the clock forward and assert the exact backoff timestamps.

## Tests

```bash
pytest
```

10 tests: dry-run delivery, idempotent retries, per-platform length validation,
unknown platform rejection, exact backoff schedule, max-attempts failure,
non-retryable errors, the retry endpoint, no double-send on a second tick, and
reclaiming a stuck `sending` row. No network access, no keys.

## What I would add with more than three hours

- A real queue (Redis/SQS) and separate worker process, so the API never blocks
  on a slow platform.
- OAuth token refresh per platform, and per-platform rate-limit budgets.
- Media attachments and per-platform formatting (threads for X, tags for Mastodon).
- Metrics on queue age and failure rate, plus a dead-letter view.
- Webhook callbacks so clients learn about a delivery without polling.
