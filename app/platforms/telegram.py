import httpx

from app.config import Settings
from app.platforms.base import PlatformError, require


class Telegram:
    """Telegram Bot API — https://core.telegram.org/bots/api#sendmessage"""

    name = "Telegram"

    def __init__(self, settings: Settings):
        self.settings = settings

    async def publish(self, message: str) -> tuple[str | None, bool]:
        token = require(self.settings.telegram_bot_token, "TELEGRAM_BOT_TOKEN")
        chat_id = require(self.settings.telegram_chat_id, "TELEGRAM_CHAT_ID")
        url = f"https://api.telegram.org/bot{token}/sendMessage"

        async with httpx.AsyncClient(timeout=self.settings.request_timeout) as client:
            try:
                resp = await client.post(
                    url,
                    json={"chat_id": chat_id, "text": message, "disable_web_page_preview": False},
                )
            except httpx.HTTPError as exc:
                raise PlatformError(f"network error: {exc}") from exc

        if resp.status_code != 200 or not resp.json().get("ok"):
            raise PlatformError(f"Telegram rejected the message: {resp.text[:200]}")

        data = resp.json()["result"]
        username = data.get("chat", {}).get("username")
        posted_url = f"https://t.me/{username}/{data['message_id']}" if username else None
        return posted_url, bool(username)
