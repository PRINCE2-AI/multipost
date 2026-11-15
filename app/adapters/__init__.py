from app.config import Settings
from app.adapters.base import Adapter, AdapterError, LIMITS
from app.adapters.devto import DevToAdapter
from app.adapters.mastodon import MastodonAdapter
from app.adapters.mock import MockAdapter
from app.adapters.telegram import TelegramAdapter

SUPPORTED = tuple(LIMITS)

__all__ = ["SUPPORTED", "LIMITS", "Adapter", "AdapterError", "get_adapter"]


def get_adapter(platform: str, settings: Settings) -> Adapter:
    if platform not in LIMITS:
        raise AdapterError(f"unknown platform: {platform}", retryable=False)
    if settings.dry_run or platform == "mock":
        return MockAdapter(settings.outbox_path, platform=platform)
    if platform == "telegram":
        return TelegramAdapter(settings.telegram_bot_token, settings.telegram_chat_id,
                               settings.request_timeout)
    if platform == "mastodon":
        return MastodonAdapter(settings.mastodon_base_url, settings.mastodon_token,
                               settings.request_timeout)
    if platform == "devto":
        return DevToAdapter(settings.devto_api_key, settings.request_timeout)
    raise AdapterError(f"no adapter for {platform}", retryable=False)
