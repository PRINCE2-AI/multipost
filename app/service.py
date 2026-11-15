import json
import uuid
from datetime import datetime, timedelta, timezone

from app.adapters import LIMITS, AdapterError, get_adapter
from app.adapters.base import now_iso
from app.config import Settings
from app.db import connect


class ValidationError(ValueError):
    def __init__(self, detail):
        super().__init__(str(detail))
        self.detail = detail


class NotFound(LookupError):
    pass


def _normalise_platforms(platforms: list[str]) -> list[str]:
    seen: list[str] = []
    for raw in platforms:
        name = raw.strip().lower()
        if name and name not in seen:
            seen.append(name)
    unknown = [p for p in seen if p not in LIMITS]
    if unknown:
        raise ValidationError({"unknown_platforms": unknown, "supported": sorted(LIMITS)})
    if not seen:
        raise ValidationError({"platforms": "at least one required"})
    return seen


def _check_lengths(content: str, platforms: list[str]) -> None:
    too_long = {p: LIMITS[p] for p in platforms if len(content) > LIMITS[p]}
    if too_long:
        raise ValidationError({
            "content_too_long": too_long,
            "content_length": len(content),
        })


def _status_for(rows) -> str:
    if not rows:
        return "scheduled"
    states = [r["status"] for r in rows]
    if all(s == "posted" for s in states):
        return "posted"
    if any(s == "pending" for s in states):
        return "partial" if any(r["attempts"] for r in rows) else "scheduled"
    return "failed"


def get_post(settings: Settings, post_id: str) -> dict:
    with connect(settings.db_path) as conn:
        post = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
        if post is None:
            raise NotFound(post_id)
        rows = conn.execute(
            "SELECT * FROM attempts WHERE post_id = ? ORDER BY platform", (post_id,)
        ).fetchall()
    return {
        "id": post["id"],
        "content": post["content"],
        "title": post["title"],
        "platforms": json.loads(post["platforms"]),
        "scheduled_at": post["scheduled_at"],
        "created_at": post["created_at"],
        "status": _status_for(rows),
        "attempts": [dict(r) for r in rows],
    }


def list_posts(settings: Settings, limit: int = 50) -> list[dict]:
    with connect(settings.db_path) as conn:
        ids = [r["id"] for r in conn.execute(
            "SELECT id FROM posts ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()]
    return [get_post(settings, pid) for pid in ids]


def create_post(settings: Settings, *, content: str, platforms: list[str],
                title: str | None = None, scheduled_at: datetime | None = None,
                idempotency_key: str | None = None) -> dict:
    content = content.strip()
    if not content:
        raise ValidationError({"content": "must not be empty"})
    names = _normalise_platforms(platforms)
    _check_lengths(content, names)

    if idempotency_key:
        with connect(settings.db_path) as conn:
            existing = conn.execute(
                "SELECT id FROM posts WHERE idempotency_key = ?", (idempotency_key,)
            ).fetchone()
        if existing:
            return get_post(settings, existing["id"])

    moment = scheduled_at or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    when = now_iso(moment)

    post_id = uuid.uuid4().hex
    created = now_iso()
    with connect(settings.db_path) as conn:
        conn.execute(
            "INSERT INTO posts (id, content, title, platforms, scheduled_at, created_at, idempotency_key)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (post_id, content, title, json.dumps(names), when, created, idempotency_key),
        )
        conn.executemany(
            "INSERT INTO attempts (post_id, platform, status, attempts, next_attempt_at, updated_at)"
            " VALUES (?, ?, 'pending', 0, ?, ?)",
            [(post_id, name, when, created) for name in names],
        )
    return get_post(settings, post_id)


def retry_post(settings: Settings, post_id: str) -> dict:
    get_post(settings, post_id)
    with connect(settings.db_path) as conn:
        cur = conn.execute(
            "UPDATE attempts SET status = 'pending', attempts = 0, next_attempt_at = ?,"
            " last_error = NULL, updated_at = ? WHERE post_id = ? AND status = 'failed'",
            (now_iso(), now_iso(), post_id),
        )
        changed = cur.rowcount
    if not changed:
        raise ValidationError({"detail": "no failed deliveries to retry"})
    return get_post(settings, post_id)


async def tick(settings: Settings, now: datetime | None = None) -> int:
    """Process every delivery attempt that is due. Returns attempts processed."""
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    now_s = now_iso(moment)

    with connect(settings.db_path) as conn:
        due = conn.execute(
            "SELECT a.post_id, a.platform, a.attempts, p.content, p.title"
            " FROM attempts a JOIN posts p ON p.id = a.post_id"
            " WHERE a.status = 'pending' AND p.scheduled_at <= ? AND a.next_attempt_at <= ?"
            " ORDER BY p.scheduled_at, a.platform",
            (now_s, now_s),
        ).fetchall()

    processed = 0
    for row in due:
        processed += 1
        attempts = row["attempts"] + 1
        try:
            adapter = get_adapter(row["platform"], settings)
            remote_id = await adapter.send(content=row["content"], title=row["title"])
        except AdapterError as exc:
            _record_failure(settings, row, attempts, str(exc), exc.retryable, exc.retry_after, moment)
        except Exception as exc:  # network hiccup, timeout, unexpected payload
            _record_failure(settings, row, attempts, f"{type(exc).__name__}: {exc}", True, None, moment)
        else:
            with connect(settings.db_path) as conn:
                conn.execute(
                    "UPDATE attempts SET status = 'posted', attempts = ?, remote_id = ?,"
                    " last_error = NULL, updated_at = ? WHERE post_id = ? AND platform = ?",
                    (attempts, remote_id, now_s, row["post_id"], row["platform"]),
                )
    return processed


def _record_failure(settings: Settings, row, attempts: int, error: str,
                    retryable: bool, retry_after: float | None, moment: datetime) -> None:
    give_up = (not retryable) or attempts >= settings.max_attempts
    if give_up:
        with connect(settings.db_path) as conn:
            conn.execute(
                "UPDATE attempts SET status = 'failed', attempts = ?, last_error = ?,"
                " updated_at = ? WHERE post_id = ? AND platform = ?",
                (attempts, error[:500], now_iso(moment), row["post_id"], row["platform"]),
            )
        return

    delay = retry_after if retry_after is not None else min(
        settings.backoff_base ** attempts, settings.backoff_cap
    )
    next_at = now_iso(moment + timedelta(seconds=delay))
    with connect(settings.db_path) as conn:
        conn.execute(
            "UPDATE attempts SET attempts = ?, last_error = ?, next_attempt_at = ?,"
            " updated_at = ? WHERE post_id = ? AND platform = ?",
            (attempts, error[:500], next_at, now_iso(moment), row["post_id"], row["platform"]),
        )
