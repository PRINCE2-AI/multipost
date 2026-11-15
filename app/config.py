import os
from dataclasses import dataclass


def _flag(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    dry_run: bool = True
    db_path: str = "var/multipost.db"
    outbox_path: str = "var/mock_outbox.jsonl"
    max_attempts: int = 5
    backoff_base: float = 2.0
    backoff_cap: float = 300.0
    scheduler_enabled: bool = True
    scheduler_interval: float = 1.0
    request_timeout: float = 15.0
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    mastodon_base_url: str | None = None
    mastodon_token: str | None = None
    devto_api_key: str | None = None


def load_settings() -> Settings:
    return Settings(
        dry_run=_flag(os.getenv("DRY_RUN"), True),
        db_path=os.getenv("DB_PATH", "var/multipost.db"),
        outbox_path=os.getenv("OUTBOX_PATH", "var/mock_outbox.jsonl"),
        max_attempts=int(os.getenv("MAX_ATTEMPTS", "5")),
        scheduler_enabled=_flag(os.getenv("SCHEDULER_ENABLED"), True),
        scheduler_interval=float(os.getenv("SCHEDULER_INTERVAL", "1.0")),
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
        telegram_chat_id=os.getenv("TELEGRAM_CHAT_ID"),
        mastodon_base_url=os.getenv("MASTODON_BASE_URL"),
        mastodon_token=os.getenv("MASTODON_TOKEN"),
        devto_api_key=os.getenv("DEVTO_API_KEY"),
    )
