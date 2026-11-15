import json
from datetime import datetime, timedelta, timezone

from app import service
from app.adapters.base import AdapterError


def test_create_post_and_deliver_in_dry_run(client, settings):
    resp = client.post("/posts", json={"content": "Hello from the queue", "platforms": ["telegram", "mastodon"]})
    assert resp.status_code == 201
    post = resp.json()
    assert post["status"] == "scheduled"
    assert len(post["attempts"]) == 2

    tick = client.post("/tick").json()
    assert tick["processed"] == 2

    body = client.get(f"/posts/{post['id']}").json()
    assert body["status"] == "posted"
    assert all(a["status"] == "posted" for a in body["attempts"])

    lines = [json.loads(line) for line in open(settings.outbox_path, encoding="utf-8")]
    assert [entry["platform"] for entry in lines] == ["mastodon", "telegram"]
    assert all(entry["remote_id"].startswith("mock-") for entry in lines)


def test_idempotency_key_returns_same_post(client):
    headers = {"Idempotency-Key": "abc-123"}
    payload = {"content": "once", "platforms": ["telegram"]}
    first = client.post("/posts", json=payload, headers=headers).json()
    second = client.post("/posts", json=payload, headers=headers).json()
    assert first["id"] == second["id"]
    assert len(client.get("/posts").json()) == 1


def test_content_too_long_for_mastodon(client):
    resp = client.post("/posts", json={"content": "x" * 600, "platforms": ["mastodon"]})
    assert resp.status_code == 422
    assert resp.json()["detail"]["content_too_long"] == {"mastodon": 500}


def test_unknown_platform_rejected(client):
    resp = client.post("/posts", json={"content": "hi", "platforms": ["myspace"]})
    assert resp.status_code == 422
    assert "myspace" in resp.json()["detail"]["unknown_platforms"]


def test_exponential_backoff_and_max_attempts(settings, monkeypatch):
    import asyncio

    from app.adapters.base import parse_iso
    from app.db import init_db

    class Boom:
        name = "telegram"
        max_length = 4096

        async def send(self, *, content, title):
            raise AdapterError("boom")

    init_db(settings.db_path)
    monkeypatch.setattr(service, "get_adapter", lambda platform, s: Boom())
    post = service.create_post(settings, content="retry me", platforms=["telegram"])

    t0 = datetime.now(timezone.utc) + timedelta(seconds=5)
    asyncio.run(service.tick(settings, now=t0))

    attempt = service.get_post(settings, post["id"])["attempts"][0]
    assert attempt["attempts"] == 1 and attempt["status"] == "pending"
    assert abs((parse_iso(attempt["next_attempt_at"]) - (t0 + timedelta(seconds=2))).total_seconds()) < 0.01

    asyncio.run(service.tick(settings, now=t0 + timedelta(seconds=1)))
    assert service.get_post(settings, post["id"])["attempts"][0]["attempts"] == 1

    moment = t0
    for _ in range(6):
        moment += timedelta(seconds=400)
        asyncio.run(service.tick(settings, now=moment))

    body = service.get_post(settings, post["id"])
    assert body["status"] == "failed"
    assert body["attempts"][0]["attempts"] == settings.max_attempts


def test_non_retryable_error_fails_immediately(client, monkeypatch):
    class Denied:
        name = "telegram"
        max_length = 4096

        async def send(self, *, content, title):
            raise AdapterError("bad token", retryable=False)

    monkeypatch.setattr(service, "get_adapter", lambda platform, s: Denied())
    post = client.post("/posts", json={"content": "nope", "platforms": ["telegram"]}).json()
    client.post("/tick")
    body = client.get(f"/posts/{post['id']}").json()
    assert body["status"] == "failed"
    assert body["attempts"][0]["attempts"] == 1
    assert "bad token" in body["attempts"][0]["last_error"]


def test_retry_endpoint_resets_failed_delivery(client, monkeypatch):
    class Denied:
        name = "telegram"
        max_length = 4096

        async def send(self, *, content, title):
            raise AdapterError("bad token", retryable=False)

    monkeypatch.setattr(service, "get_adapter", lambda platform, s: Denied())
    post = client.post("/posts", json={"content": "again", "platforms": ["telegram"]}).json()
    client.post("/tick")
    assert client.get(f"/posts/{post['id']}").json()["status"] == "failed"

    monkeypatch.undo()
    retried = client.post(f"/posts/{post['id']}/retry").json()
    assert retried["attempts"][0]["status"] == "pending"
    client.post("/tick")
    assert client.get(f"/posts/{post['id']}").json()["status"] == "posted"


def test_health_and_platforms(client):
    health = client.get("/health").json()
    assert health["status"] == "ok" and health["dry_run"] is True
    supported = client.get("/platforms").json()["supported"]
    assert {"telegram", "mastodon", "devto", "mock"} <= set(supported)
