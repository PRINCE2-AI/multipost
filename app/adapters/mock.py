import json
import os
import uuid

from app.adapters.base import now_iso


class MockAdapter:
    """Writes to a JSONL outbox instead of calling a real API.

    Used when DRY_RUN=1 (the default), so the whole pipeline can be reviewed and
    tested before any credentials exist.
    """

    name = "mock"
    max_length = 100_000

    def __init__(self, outbox_path: str, platform: str = "mock"):
        self.outbox_path = outbox_path
        self.platform = platform

    async def send(self, *, content: str, title: str | None) -> str:
        parent = os.path.dirname(self.outbox_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        remote_id = f"mock-{uuid.uuid4().hex[:8]}"
        record = {
            "at": now_iso(),
            "platform": self.platform,
            "title": title,
            "content": content,
            "remote_id": remote_id,
        }
        with open(self.outbox_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")
        return remote_id
