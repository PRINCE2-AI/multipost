from datetime import datetime, timezone

import httpx

from app.config import Settings
from app.platforms.base import PlatformError, require
from app.validation import URL_RE


def link_facets(text: str) -> list[dict]:
    """Byte offsets are required by the AT Protocol, not character offsets."""
    facets = []
    for match in URL_RE.finditer(text):
        url = match.group(0)
        start = len(text[:match.start()].encode("utf-8"))
        end = start + len(url.encode("utf-8"))
        facets.append({
            "index": {"byteStart": start, "byteEnd": end},
            "features": [{"$type": "app.bsky.richtext.facet#link", "uri": url}],
        })
    return facets


class Bluesky:
    """AT Protocol — https://docs.bsky.app/docs/advanced-guides/posts"""

    name = "Bluesky"

    def __init__(self, settings: Settings):
        self.settings = settings

    async def publish(self, message: str) -> tuple[str | None, bool]:
        handle = require(self.settings.bluesky_handle, "BLUESKY_HANDLE")
        password = require(self.settings.bluesky_app_password, "BLUESKY_APP_PASSWORD")
        pds = self.settings.bluesky_pds.rstrip("/")

        async with httpx.AsyncClient(timeout=self.settings.request_timeout) as client:
            try:
                session_resp = await client.post(
                    f"{pds}/xrpc/com.atproto.server.createSession",
                    json={"identifier": handle, "password": password},
                )
                if session_resp.status_code != 200:
                    raise PlatformError(f"Bluesky login failed: {session_resp.text[:200]}")
                session = session_resp.json()

                record = {
                    "$type": "app.bsky.feed.post",
                    "text": message,
                    "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                }
                facets = link_facets(message)
                if facets:
                    record["facets"] = facets

                write_resp = await client.post(
                    f"{pds}/xrpc/com.atproto.repo.createRecord",
                    headers={"Authorization": f"Bearer {session['accessJwt']}"},
                    json={
                        "repo": session["did"],
                        "collection": "app.bsky.feed.post",
                        "record": record,
                    },
                )
            except httpx.HTTPError as exc:
                raise PlatformError(f"network error: {exc}") from exc

        if write_resp.status_code != 200:
            raise PlatformError(f"Bluesky rejected the post: {write_resp.text[:200]}")

        uri = write_resp.json()["uri"]
        rkey = uri.rsplit("/", 1)[-1]
        return f"https://bsky.app/profile/{handle}/post/{rkey}", True
