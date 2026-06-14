"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # Application
    secret_key: str = Field(..., description="Secret key for signing sessions/cookies")
    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/app.db",
        description="SQLAlchemy database URL",
    )

    # LinkedIn OAuth 2.0
    linkedin_client_id: str = Field(..., description="LinkedIn app client ID")
    linkedin_client_secret: str = Field(..., description="LinkedIn app client secret")
    linkedin_redirect_uri: str = Field(
        default="http://localhost:8000/auth/linkedin/callback",
        description="OAuth redirect URI registered with LinkedIn",
    )

    # OpenAI
    openai_api_key: str = Field(..., description="OpenAI API key")
    openai_model: str = Field(default="gpt-4o-mini", description="OpenAI model name")
    openai_api_base: str | None = Field(
        default=None,
        description="OpenAI-compatible API base URL (e.g. https://generativelanguage.googleapis.com/v1beta/openai/ for Gemini)",
    )

    # GitHub
    github_username: str | None = Field(
        default=None,
        description="GitHub username to fetch repositories for Monday project spotlight posts",
    )

    # Scheduling
    timezone: str = Field(default="America/Phoenix", description="Timezone for scheduling")
    schedule_hour: int = Field(default=10, description="Hour to run daily job (0-23)")
    schedule_minute: int = Field(default=0, description="Minute to run daily job (0-59)")

    # Encryption
    fernet_key: str = Field(..., description="Fernet key for token encryption")

    # LinkedIn API endpoints
    linkedin_auth_url: str = "https://www.linkedin.com/oauth/v2/authorization"
    linkedin_token_url: str = "https://www.linkedin.com/oauth/v2/accessToken"
    linkedin_userinfo_url: str = "https://api.linkedin.com/v2/userinfo"
    linkedin_posts_url: str = "https://api.linkedin.com/rest/posts"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


def get_settings() -> Settings:
    return Settings()
