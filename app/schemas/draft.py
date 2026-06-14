"""Draft-related schemas."""

from typing import Literal

from pydantic import BaseModel


class DraftResponse(BaseModel):
    id: int
    content: str
    word_count: int
    char_count: int
    tone: str
    compliance_passed: bool
    created_at: str
    date_for: str


class RewriteRequest(BaseModel):
    draft_id: int
    tone: Literal[
        "professional",
        "simple",
        "shorter",
        "more_engaging",
        "more_technical",
    ]
