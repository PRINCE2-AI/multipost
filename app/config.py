import os
from dataclasses import dataclass

from dotenv import load_dotenv


def _flag(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


DEFAULT_PLATFORMS = ("telegram", "mastodon", "bluesky", "devto", "discord", "slack")


@dataclass
class Settings:
    dry_run: bool = True
    request_timeout: float = 15.0
    enabled_platforms: tuple[str, ...] = DEFAULT_PLATFORMS

    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None

    mastodon_base_url: str | None = None
    mastodon_token: str | None = None

    bluesky_pds: str = "https://bsky.social"
    bluesky_handle: str | None = None
    bluesky_app_password: str | None = None

    devto_api_key: str | None = None

    discord_webhook_url: str | None = None
    slack_webhook_url: str | None = None


def load_settings() -> Settings:
    load_dotenv()
    enabled = os.getenv("ENABLED_PLATFORMS")
    platforms = tuple(p.strip().lower() for p in enabled.split(",") if p.strip()) if enabled else DEFAULT_PLATFORMS
    return Settings(
        dry_run=_flag(os.getenv("DRY_RUN"), True),
        request_timeout=float(os.getenv("REQUEST_TIMEOUT", "15")),
        enabled_platforms=platforms,
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID"),
        mastodon_base_url=os.getenv("MASTODON_BASE_URL"),
        mastodon_token=os.getenv("MASTODON_TOKEN"),
        bluesky_pds=os.getenv("BLUESKY_PDS", "https://bsky.social"),
        bluesky_handle=os.getenv("BLUESKY_HANDLE"),
        bluesky_app_password=os.getenv("BLUESKY_APP_PASSWORD"),
        devto_api_key=os.getenv("DEVTO_API_KEY"),
        discord_webhook_url=os.getenv("DISCORD_WEBHOOK_URL"),
        slack_webhook_url=os.getenv("SLACK_WEBHOOK_URL"),
    )
