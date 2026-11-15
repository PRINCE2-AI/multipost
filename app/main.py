import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException, Request

from app import scheduler, service
from app.adapters import LIMITS
from app.config import Settings, load_settings
from app.db import connect, init_db
from app.schemas import PostIn, PostOut

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or load_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_db(settings.db_path)
        task = None
        if settings.scheduler_enabled:
            task = asyncio.create_task(scheduler.run_forever(settings))
        try:
            yield
        finally:
            if task:
                task.cancel()

    app = FastAPI(
        title="Multi-Platform Posting System",
        version="1.0.0",
        description="Queue content once, deliver it to several platforms independently, "
                    "with per-platform retries and idempotency.",
        lifespan=lifespan,
    )
    app.state.settings = settings

    def cfg(request: Request) -> Settings:
        return request.app.state.settings

    @app.get("/")
    def root():
        return {"service": "multipost", "docs": "/docs", "dry_run": settings.dry_run}

    @app.get("/health")
    def health(request: Request):
        s = cfg(request)
        try:
            with connect(s.db_path) as conn:
                posts = conn.execute("SELECT COUNT(*) AS n FROM posts").fetchone()["n"]
                pending = conn.execute(
                    "SELECT COUNT(*) AS n FROM attempts WHERE status = 'pending'"
                ).fetchone()["n"]
        except Exception as exc:
            raise HTTPException(503, f"database unavailable: {exc}")
        return {"status": "ok", "dry_run": s.dry_run, "posts": posts, "pending": pending}

    @app.post("/posts", response_model=PostOut, status_code=201)
    def create_post(
        payload: PostIn,
        request: Request,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ):
        try:
            return service.create_post(
                cfg(request),
                content=payload.content,
                platforms=payload.platforms,
                title=payload.title,
                scheduled_at=payload.scheduled_at,
                idempotency_key=idempotency_key,
            )
        except service.ValidationError as exc:
            raise HTTPException(422, exc.detail)

    @app.get("/posts", response_model=list[PostOut])
    def list_posts(request: Request, limit: int = 50):
        return service.list_posts(cfg(request), min(max(limit, 1), 200))

    @app.get("/posts/{post_id}", response_model=PostOut)
    def read_post(post_id: str, request: Request):
        try:
            return service.get_post(cfg(request), post_id)
        except service.NotFound:
            raise HTTPException(404, "post not found")

    @app.post("/posts/{post_id}/retry", response_model=PostOut)
    def retry_post(post_id: str, request: Request):
        try:
            return service.retry_post(cfg(request), post_id)
        except service.NotFound:
            raise HTTPException(404, "post not found")
        except service.ValidationError as exc:
            raise HTTPException(409, exc.detail)

    @app.post("/tick")
    async def run_tick(request: Request):
        processed = await service.tick(cfg(request))
        return {"processed": processed}

    @app.get("/platforms")
    def platforms():
        return {"supported": sorted(LIMITS), "max_length": LIMITS}

    return app


app = create_app()
