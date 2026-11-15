import httpx

from app.config import Settings
from app.platforms.base import PlatformError, require
from app.validation import URL_RE

MAX_TITLE = 80


def title_for(message: str) -> str:
    """Dev.to requires a title; the contract only sends a message, so derive one."""
    without_link = URL_RE.sub("", message).strip(" -:—")
    first_line = without_link.split("\n", 1)[0].strip()
    title = first_line or "New post"
    return title if len(title) <= MAX_TITLE else title[: MAX_TITLE - 3].rstrip() + "..."


class DevTo:
    """Forem/Dev.to API — https://developers.forem.com/api/v1#tag/articles"""

    name = "Dev.to"

    def __init__(self, settings: Settings):
        self.settings = settings

    async def publish(self, message: str) -> tuple[str | None, bool]:
        api_key = require(self.settings.devto_api_key, "DEVTO_API_KEY")

        async with httpx.AsyncClient(timeout=self.settings.request_timeout) as client:
            try:
                resp = await client.post(
                    "https://dev.to/api/articles",
                    headers={"api-key": api_key},
                    json={"article": {
                        "title": title_for(message),
                        "body_markdown": message,
                        "published": True,
                    }},
                )
            except httpx.HTTPError as exc:
                raise PlatformError(f"network error: {exc}") from exc

        if resp.status_code not in (200, 201):
            raise PlatformError(f"Dev.to {resp.status_code}: {resp.text[:200]}")

        article = resp.json()
        return article.get("url"), article.get("published") is True
