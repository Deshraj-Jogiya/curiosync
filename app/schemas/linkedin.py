"""LinkedIn publish response schema."""

from pydantic import BaseModel


class PublishResponse(BaseModel):
    success: bool
    linkedin_post_id: str | None = None
    error: str | None = None
