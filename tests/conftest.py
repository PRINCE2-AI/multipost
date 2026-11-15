import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import Settings  # noqa: E402
from app.db import init_db  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture
def settings(tmp_path):
    return Settings(
        dry_run=True,
        db_path=str(tmp_path / "test.db"),
        outbox_path=str(tmp_path / "outbox.jsonl"),
        scheduler_enabled=False,
        max_attempts=5,
        backoff_base=2.0,
        backoff_cap=300.0,
    )


@pytest.fixture
def client(settings):
    init_db(settings.db_path)
    with TestClient(create_app(settings)) as c:
        yield c
