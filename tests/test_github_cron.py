"""Tests for the standalone GitHub Actions cron script."""

import os
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.database import async_session
from app.models.token import OAuthToken
from app.models.user import User
from github_cron import main


@pytest.mark.asyncio
@patch("github_cron.run_daily_pipeline")
@patch("sys.exit")
async def test_github_cron_successful_run(mock_exit, mock_pipeline):
    """Test github_cron.py successfully parses environment, seeds database, and triggers run."""
    # Mock return value of run_daily_pipeline
    mock_pipeline.return_value = {"status": "success", "steps": {"mock_step": "completed"}}

    # Mock environment variables
    env_mock = {
        "LINKEDIN_ACCESS_TOKEN": "mock-access-token-123",
        "LINKEDIN_SUB_URN": "urn:li:person:mock-sub-456",
        "OPENAI_API_KEY": "mock-openai-key",
        "SECRET_KEY": "test-secret",
        "LINKEDIN_CLIENT_ID": "test-id",
        "LINKEDIN_CLIENT_SECRET": "test-secret",
        "FERNET_KEY": "On9Xt3DeuvikAzn4c-yVjMCAyVAJJXGvKAh6rOstuUU=",
        "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
    }

    with patch.dict(os.environ, env_mock):
        await main()

    # Verify sys.exit(0) was called
    mock_exit.assert_called_once_with(0)

    # Verify that the User and OAuthToken tables were correctly populated in-memory
    async with async_session() as session:
        # Check User
        user_res = await session.execute(select(User).where(User.linkedin_sub == "mock-sub-456"))
        user = user_res.scalar_one_or_none()
        assert user is not None
        user_id = user.id

        # Check Token
        token_res = await session.execute(select(OAuthToken).where(OAuthToken.user_id == user_id))
        token = token_res.scalar_one_or_none()
        assert token is not None

    # Verify run_daily_pipeline was called with the correct user_id
    mock_pipeline.assert_called_once_with(user_id=user_id, run_type="github_actions_cron")

    # Verify it decrypts back to the mock access token
    settings = get_settings()
    decrypted = token.decrypt_access_token(settings.fernet_key)
    assert decrypted == "mock-access-token-123"


@pytest.mark.asyncio
@patch("github_cron.run_daily_pipeline")
@patch("sys.exit")
async def test_github_cron_failure_run(mock_exit, mock_pipeline):
    """Test github_cron.py handles pipeline failure and exits with 1."""
    mock_pipeline.return_value = {
        "status": "failed",
        "error": "API error",
        "steps": {"some_step": "failed"},
    }

    env_mock = {
        "LINKEDIN_ACCESS_TOKEN": "mock-access-token-123",
        "LINKEDIN_SUB_URN": "urn:li:person:mock-sub-456",
        "OPENAI_API_KEY": "mock-openai-key",
        "SECRET_KEY": "test-secret",
        "LINKEDIN_CLIENT_ID": "test-id",
        "LINKEDIN_CLIENT_SECRET": "test-secret",
        "FERNET_KEY": "On9Xt3DeuvikAzn4c-yVjMCAyVAJJXGvKAh6rOstuUU=",
        "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
    }

    with patch.dict(os.environ, env_mock):
        await main()

    mock_exit.assert_called_once_with(1)


@pytest.mark.asyncio
@patch("sys.exit")
async def test_github_cron_missing_env(mock_exit):
    """Test github_cron.py exits with 1 if environment variables are missing."""
    env_mock = {
        "LINKEDIN_ACCESS_TOKEN": "",
        "LINKEDIN_SUB_URN": "urn:li:person:mock-sub-456",
        "OPENAI_API_KEY": "mock-openai-key",
        "SECRET_KEY": "test-secret",
        "LINKEDIN_CLIENT_ID": "test-id",
        "LINKEDIN_CLIENT_SECRET": "test-secret",
        "FERNET_KEY": "On9Xt3DeuvikAzn4c-yVjMCAyVAJJXGvKAh6rOstuUU=",
        "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
    }

    with patch.dict(os.environ, env_mock):
        await main()

    mock_exit.assert_called_once_with(1)
