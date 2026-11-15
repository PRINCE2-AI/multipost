import asyncio
from datetime import datetime, timezone

from app.config import Settings
from app.platforms import build_platforms
from app.platforms.base import PlatformError
from app.schemas import PlatformResultOut, PostingResponse


async def publish_everywhere(settings: Settings, message: str) -> PostingResponse:
    """Fan out to every configured platform and never let one failure stop the rest."""
    platforms = build_platforms(settings)
    results = await asyncio.gather(
        *(_publish_one(platform, message, settings.dry_run) for platform in platforms)
    )
    success = any(result.status != "failed" for result in results)
    return PostingResponse(success=success, dry_run=settings.dry_run, results=list(results))


async def _publish_one(platform, message: str, dry_run: bool) -> PlatformResultOut:
    if dry_run:
        return PlatformResultOut(platform=platform.name, status="dry_run")

    try:
        posted_url, public_access = await platform.publish(message)
    except PlatformError as exc:
        return PlatformResultOut(platform=platform.name, status="failed", error=str(exc))
    except Exception as exc:  # an adapter bug must not take down the other platforms
        return PlatformResultOut(
            platform=platform.name, status="failed", error=f"{type(exc).__name__}: {exc}"
        )

    now = datetime.now(timezone.utc)
    return PlatformResultOut(
        platform=platform.name,
        status="success",
        posted_url=posted_url,
        public_access=public_access,
        date=now.date().isoformat(),
        time=now.strftime("%H:%M:%S"),
    )
