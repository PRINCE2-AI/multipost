import asyncio

import pytest

from app import main
from app.config import Settings
from app.platforms.base import PlatformError
from app.services import posting_service

GOOD = "Check out our latest business platform and grow your online visibility. https://example.com"
RESULT_KEYS = {"platform", "status", "posted_url", "public_access", "date", "time", "error"}


def post(client, message):
    return client.post("/posting", json={"message": message})


def test_dry_run_reports_every_platform_with_the_contract_fields(client):
    resp = post(client, GOOD)
    assert resp.status_code == 200
    body = resp.json()
    assert body["dry_run"] is True
    assert body["success"] is True
    assert len(body["results"]) == 6
    for result in body["results"]:
        assert set(result) == RESULT_KEYS
        assert result["status"] == "dry_run"
        assert result["posted_url"] is None
        assert result["public_access"] is False
    assert {r["platform"] for r in body["results"]} == {
        "Telegram", "Mastodon", "Bluesky", "Dev.to", "Discord", "Slack",
    }


def test_message_longer_than_200_characters_is_rejected(client):
    resp = post(client, "a" * 190 + " https://example.com")
    assert resp.status_code == 422
    assert resp.json()["detail"]["length"] > 200


def test_exactly_200_characters_is_accepted(client):
    link = " https://example.com"
    resp = post(client, "a" * (200 - len(link)) + link)
    assert resp.status_code == 200


def test_missing_link_is_rejected(client):
    resp = post(client, "No link in this message")
    assert resp.status_code == 422
    assert resp.json()["detail"]["links_found"] == 0


def test_two_links_are_rejected(client):
    resp = post(client, "https://example.com and https://example.org")
    assert resp.status_code == 422
    assert resp.json()["detail"]["links_found"] == 2


def test_link_without_a_host_is_rejected(client):
    resp = post(client, "click https://localhost")
    assert resp.status_code == 422
    assert "valid" in resp.json()["detail"]["message"]


def test_empty_message_is_rejected(client):
    assert post(client, "   ").status_code == 422


class FakePlatform:
    def __init__(self, name, result=None, error=None):
        self.name = name
        self._result = result
        self._error = error

    async def publish(self, message):
        if self._error:
            raise PlatformError(self._error)
        return self._result


def run_with(monkeypatch, platforms, message=GOOD):
    monkeypatch.setattr(posting_service, "build_platforms", lambda settings: platforms)
    return asyncio.run(posting_service.publish_everywhere(Settings(dry_run=False), message))


def test_one_failing_platform_does_not_stop_the_others(monkeypatch):
    response = run_with(monkeypatch, [
        FakePlatform("Telegram", ("https://t.me/demo/1", True)),
        FakePlatform("Mastodon", error="Authentication failed"),
        FakePlatform("Slack", (None, False)),
    ])
    assert response.success is True
    results = {r.platform: r for r in response.results}

    assert results["Telegram"].status == "success"
    assert results["Telegram"].posted_url == "https://t.me/demo/1"
    assert results["Telegram"].public_access is True
    assert results["Telegram"].date and results["Telegram"].time

    assert results["Mastodon"].status == "failed"
    assert results["Mastodon"].error == "Authentication failed"
    assert results["Mastodon"].posted_url is None
    assert results["Mastodon"].date is None

    assert results["Slack"].status == "success"  # published, but no public URL exists
    assert results["Slack"].posted_url is None


def test_all_platforms_failing_reports_success_false(monkeypatch):
    response = run_with(monkeypatch, [
        FakePlatform("Telegram", error="bad token"),
        FakePlatform("Mastodon", error="bad token"),
    ])
    assert response.success is False
    assert [r.status for r in response.results] == ["failed", "failed"]


def test_unexpected_adapter_exception_is_contained(monkeypatch):
    class Boom:
        name = "Discord"

        async def publish(self, message):
            raise ValueError("unexpected payload")

    response = run_with(monkeypatch, [FakePlatform("Telegram", ("https://t.me/x/1", True)), Boom()])
    results = {r.platform: r for r in response.results}
    assert results["Telegram"].status == "success"
    assert results["Discord"].status == "failed"
    assert "unexpected payload" in results["Discord"].error


def test_missing_credentials_are_reported_per_platform(monkeypatch):
    class NeedsKey:
        name = "Bluesky"

        async def publish(self, message):
            from app.platforms.base import require

            require(None, "BLUESKY_APP_PASSWORD")
            return None, False

    response = run_with(monkeypatch, [NeedsKey()])
    assert response.results[0].status == "failed"
    assert response.results[0].error == "BLUESKY_APP_PASSWORD is not set"


def test_health_and_platforms(client):
    health = client.get("/health").json()
    assert health["status"] == "ok" and health["dry_run"] is True
    listed = client.get("/platforms").json()
    assert listed["max_message_length"] == 200
    assert "bluesky" in listed["platforms"]


def test_unknown_platform_name_fails_at_startup():
    from fastapi.testclient import TestClient

    with pytest.raises(RuntimeError):
        with TestClient(main.create_app(Settings(enabled_platforms=("myspace",)))):
            pass
