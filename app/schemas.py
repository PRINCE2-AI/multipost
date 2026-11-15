from typing import Literal

from pydantic import BaseModel, Field


class PostingRequest(BaseModel):
    message: str = Field(min_length=1, description="Text to publish, max 200 characters, exactly one link")


class PlatformResultOut(BaseModel):
    platform: str
    status: Literal["success", "failed", "dry_run"]
    posted_url: str | None = None
    public_access: bool = False
    date: str | None = None
    time: str | None = None
    error: str | None = None


class PostingResponse(BaseModel):
    success: bool
    dry_run: bool = False
    results: list[PlatformResultOut]
