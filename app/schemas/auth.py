"""Auth-related response schemas."""

from pydantic import BaseModel


class AuthStatus(BaseModel):
    linkedin_connected: bool
    user_name: str | None = None
    token_expires_at: str | None = None
    token_expired: bool = False
    token_expires_soon: bool = False
