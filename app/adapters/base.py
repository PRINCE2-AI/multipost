from datetime import datetime, timezone
from typing import Protocol


class AdapterError(Exception):
    def __init__(self, message: str, *, retryable: bool = True, retry_after: float | None = None):
        super().__init__(message)
        self.retryable = retryable
        self.retry_after = retry_after


class Adapter(Protocol):
    name: str
    max_length: int

    async def send(self, *, content: str, title: str | None) -> str: ...


LIMITS: dict[str, int] = {
    "telegram": 4096,
    "mastodon": 500,
    "devto": 60_000,
    "mock": 100_000,
}


def now_iso(moment: datetime | None = None) -> str:
    moment = moment or datetime.now(timezone.utc)
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def parse_iso(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
