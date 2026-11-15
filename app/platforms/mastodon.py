import httpx

from app.config import Settings
from app.platforms.base import PlatformError, require


class Mastodon:
    """Mastodon REST API — https://docs.joinmastodon.org/methods/statuses/#create"""

    name = "Mastodon"

    def __init__(self, settings: Settings):
        self.settings = settings

    async def publish(self, message: str) -> tuple[str | None, bool]:
        base = require(self.settings.mastodon_base_url, "MASTODON_BASE_URL").rstrip("/")
        token = require(self.settings.mastodon_token, "MASTODON_TOKEN")

        async with httpx.AsyncClient(timeout=self.settings.request_timeout) as client:
            try:
                resp = await client.post(
                    f"{base}/api/v1/statuses",
                    headers={"Authorization": f"Bearer {token}"},
                    json={"status": message, "visibility": "public"},
                )
            except httpx.HTTPError as exc:
                raise PlatformError(f"network error: {exc}") from exc

        if resp.status_code != 200:
            raise PlatformError(f"Mastodon {resp.status_code}: {resp.text[:200]}")

        status = resp.json()
        return status.get("url"), status.get("visibility") == "public"
