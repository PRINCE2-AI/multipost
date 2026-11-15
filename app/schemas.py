from datetime import datetime

from pydantic import BaseModel, Field


class PostIn(BaseModel):
    content: str = Field(min_length=1)
    platforms: list[str] = Field(min_length=1)
    title: str | None = None
    scheduled_at: datetime | None = None


class AttemptOut(BaseModel):
    platform: str
    status: str
    attempts: int
    next_attempt_at: str
    last_error: str | None
    remote_id: str | None
    updated_at: str


class PostOut(BaseModel):
    id: str
    content: str
    title: str | None
    platforms: list[str]
    scheduled_at: str
    created_at: str
    status: str
    attempts: list[AttemptOut]
