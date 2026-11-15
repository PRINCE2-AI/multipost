import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import Settings  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture
def settings() -> Settings:
    return Settings(dry_run=True, request_timeout=2.0)


@pytest.fixture
def client(settings):
    with TestClient(create_app(settings)) as test_client:
        yield test_client
