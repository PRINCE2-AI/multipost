import asyncio
import logging

from app.config import Settings
from app.service import tick

log = logging.getLogger("multipost.scheduler")


async def run_forever(settings: Settings) -> None:
    while True:
        try:
            processed = await tick(settings)
            if processed:
                log.info("processed %d delivery attempts", processed)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("scheduler tick failed")
        await asyncio.sleep(settings.scheduler_interval)
