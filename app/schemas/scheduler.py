"""Scheduler status schema."""

from pydantic import BaseModel


class SchedulerStatus(BaseModel):
    running: bool
    next_run: str | None = None
    last_success: str | None = None
    last_failure: str | None = None
    token_status: str = "unknown"
