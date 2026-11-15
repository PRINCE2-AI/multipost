import os
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    id              TEXT PRIMARY KEY,
    content         TEXT NOT NULL,
    title           TEXT,
    platforms       TEXT NOT NULL,
    scheduled_at    TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    idempotency_key TEXT UNIQUE
);

CREATE TABLE IF NOT EXISTS attempts (
    post_id         TEXT NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
    platform        TEXT NOT NULL,
    status          TEXT NOT NULL,
    attempts        INTEGER NOT NULL DEFAULT 0,
    next_attempt_at TEXT NOT NULL,
    last_error      TEXT,
    remote_id       TEXT,
    updated_at      TEXT NOT NULL,
    PRIMARY KEY (post_id, platform)
);

CREATE INDEX IF NOT EXISTS idx_attempts_due
    ON attempts (status, next_attempt_at);
"""


class Connection(sqlite3.Connection):
    """Autocommit connection that also closes itself at the end of a `with` block."""

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type is None:
                self.commit()
            else:
                self.rollback()
        finally:
            self.close()
        return False


def connect(path: str) -> Connection:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10, isolation_level=None, factory=Connection)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(path: str) -> None:
    with connect(path) as conn:
        conn.executescript(SCHEMA)
