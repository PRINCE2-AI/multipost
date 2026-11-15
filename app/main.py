from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request

from app.config import Settings, load_settings
from app.platforms import REGISTRY
from app.schemas import PostingRequest, PostingResponse
from app.services.posting_service import publish_everywhere
from app.validation import MAX_LENGTH, MessageError, validate_message


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        unknown = [name for name in settings.enabled_platforms if name not in REGISTRY]
        if unknown:
            raise RuntimeError(f"unknown platforms in ENABLED_PLATFORMS: {', '.join(unknown)}")
        yield

    app = FastAPI(
        title="Automated Multi-Platform Posting System",
        version="1.0.0",
        description=(
            "Publish one short message with a call-to-action link to Telegram, Mastodon, "
            "Bluesky, Dev.to, Discord and Slack. Each platform is posted independently "
            "and reported separately."
        ),
        lifespan=lifespan,
    )
    app.state.settings = settings

    @app.get("/health")
    def health(request: Request) -> dict:
        active: Settings = request.app.state.settings
        return {
            "status": "ok",
            "dry_run": active.dry_run,
            "platforms": list(active.enabled_platforms),
        }

    @app.get("/platforms")
    def platforms() -> dict:
        return {"platforms": list(settings.enabled_platforms), "max_message_length": MAX_LENGTH}

    @app.post("/posting", response_model=PostingResponse)
    async def posting(payload: PostingRequest, request: Request) -> PostingResponse:
        try:
            message = validate_message(payload.message)
        except MessageError as exc:
            raise HTTPException(status_code=422, detail=exc.detail)
        return await publish_everywhere(request.app.state.settings, message)

    return app


app = create_app()
