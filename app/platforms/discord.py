import httpx

from app.config import Settings
from app.platforms.base import PlatformError, require


class Discord:
    """Discord webhook — https://discord.com/developers/docs/resources/webhook#execute-webhook"""

    name = "Discord"

    def __init__(self, settings: Settings):
        self.settings = settings

    async def publish(self, message: str) -> tuple[str | None, bool]:
        webhook = require(self.settings.discord_webhook_url, "DISCORD_WEBHOOK_URL")
        separator = "&" if "?" in webhook else "?"

        async with httpx.AsyncClient(timeout=self.settings.request_timeout) as client:
            try:
                resp = await client.post(f"{webhook}{separator}wait=true", json={"content": message})
            except httpx.HTTPError as exc:
                raise PlatformError(f"network error: {exc}") from exc

        if resp.status_code not in (200, 204):
            raise PlatformError(f"Discord {resp.status_code}: {resp.text[:200]}")

        data = resp.json() if resp.content else {}
        guild_id, channel_id, message_id = data.get("guild_id"), data.get("channel_id"), data.get("id")
        posted_url = (
            f"https://discord.com/channels/{guild_id}/{channel_id}/{message_id}"
            if guild_id and channel_id and message_id else None
        )
        # A webhook can post to a private channel, so public access cannot be asserted.
        return posted_url, False
