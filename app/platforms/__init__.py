from typing import Protocol

from app.config import Settings
from app.platforms.bluesky import Bluesky
from app.platforms.devto import DevTo
from app.platforms.discord import Discord
from app.platforms.mastodon import Mastodon
from app.platforms.slack import Slack
from app.platforms.telegram import Telegram


class Platform(Protocol):
    name: str

    async def publish(self, message: str) -> tuple[str | None, bool]:
        """Publish and return (posted_url, public_access). Raise PlatformError on failure."""


class DryRun:
    """Stands in for a real integration when DRY_RUN=1: no credentials, no network."""

    def __init__(self, name: str):
        self.name = name

    async def publish(self, message: str) -> tuple[str | None, bool]:
        return None, False


REGISTRY: dict[str, type] = {
    "telegram": Telegram,
    "mastodon": Mastodon,
    "bluesky": Bluesky,
    "devto": DevTo,
    "discord": Discord,
    "slack": Slack,
}


def build_platforms(settings: Settings) -> list[Platform]:
    unknown = [name for name in settings.enabled_platforms if name not in REGISTRY]
    if unknown:
        raise ValueError(f"unknown platforms in ENABLED_PLATFORMS: {', '.join(unknown)}")

    if settings.dry_run:
        return [DryRun(REGISTRY[name].name) for name in settings.enabled_platforms]
    return [REGISTRY[name](settings) for name in settings.enabled_platforms]
