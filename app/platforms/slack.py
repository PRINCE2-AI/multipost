import httpx

from app.config import Settings
from app.platforms.base import PlatformError, require


class Slack:
    """Slack incoming webhook — https://api.slack.com/messaging/webhooks"""

    name = "Slack"

    def __init__(self, settings: Settings):
        self.settings = settings

    async def publish(self, message: str) -> tuple[str | None, bool]:
        webhook = require(self.settings.slack_webhook_url, "SLACK_WEBHOOK_URL")

        async with httpx.AsyncClient(timeout=self.settings.request_timeout) as client:
            try:
                resp = await client.post(webhook, json={"text": message})
            except httpx.HTTPError as exc:
                raise PlatformError(f"network error: {exc}") from exc

        if resp.status_code != 200 or resp.text.strip() != "ok":
            raise PlatformError(f"Slack {resp.status_code}: {resp.text[:200]}")

        # Incoming webhooks return no message identifier or public URL.
        return None, False
