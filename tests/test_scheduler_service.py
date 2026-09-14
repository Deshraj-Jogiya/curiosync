"""Tests for run_daily_pipeline's draft-format branching.

generate_monday_project_spotlight existed, was fully built and tested, but was
never actually invoked by the real daily pipeline -- every scheduled post used
the news-hook format, every day, with no rotation. These tests lock in the fix:
Mondays use the project-spotlight format, every other day uses the news-hook
format, so the feed isn't 100% identical structure day after day.
"""

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from app.config import Settings
from app.models.user import User
from app.services.scheduler_service import run_daily_pipeline


def _settings() -> Settings:
    return Settings(
        secret_key="test-secret",
        linkedin_client_id="test-client-id",
        linkedin_client_secret="test-client-secret",
        fernet_key="s2v9G8QGuF9jS8g5T5Q5f5f5f5f5f5f5f5f5f5f5f4=",
        database_url="sqlite+aiosqlite:///:memory:",
        openai_api_key="test-key",
        github_username="Deshraj-Jogiya",
    )


async def _seed_user(test_db) -> int:
    user = User(linkedin_sub="test-sub", name="Test User", email="test@example.com")
    test_db.add(user)
    await test_db.flush()
    return user.id


def _patch_common(monday: date):
    """Patch every scheduler_service dependency except draft generation itself."""
    return [
        patch("app.services.scheduler_service.get_today_post", AsyncMock(return_value=None)),
        patch("app.services.scheduler_service.get_valid_token", AsyncMock(return_value="fake-token")),
        patch("app.services.scheduler_service.fetch_news", AsyncMock(return_value=[{"title": "x", "source_name": "y"}])),
        patch("app.services.scheduler_service.save_news_items", AsyncMock(return_value=None)),
        patch("app.services.scheduler_service.check_compliance", lambda text, items: {"passed": True, "issues": []}),
        patch("app.services.scheduler_service.humanize_draft", lambda text: text),
        patch("app.services.scheduler_service.publish_post", AsyncMock(return_value={"success": True, "post_id": "123"})),
        patch("app.services.scheduler_service.record_post", AsyncMock(return_value=None)),
        patch("app.services.scheduler_service.today_phoenix", lambda: monday),
        patch("app.services.image_service.generate_graphic_metadata", AsyncMock(return_value={})),
        patch("app.services.image_service.generate_linkedin_image", lambda *a, **k: None),
        patch("app.services.scheduler_service.fetch_github_projects", AsyncMock(return_value=[])),
    ]


@pytest.mark.asyncio
async def test_monday_uses_project_spotlight(test_db):
    """On a Monday, the pipeline must call the spotlight generator, not the news-hook one."""
    user_id = await _seed_user(test_db)
    monday = date(2026, 9, 14)  # a real Monday
    assert monday.weekday() == 0

    patches = _patch_common(monday)
    with patch(
        "app.services.scheduler_service.generate_monday_project_spotlight",
        AsyncMock(return_value="spotlight draft"),
    ) as mock_spotlight, patch(
        "app.services.scheduler_service.generate_draft", AsyncMock(return_value="news draft")
    ) as mock_news_draft:
        for p in patches:
            p.start()
        try:
            result = await run_daily_pipeline(user_id=user_id, db=test_db, settings=_settings(), run_type="manual")
        finally:
            for p in patches:
                p.stop()

    assert result["status"] == "success"
    mock_spotlight.assert_awaited_once()
    mock_news_draft.assert_not_awaited()


@pytest.mark.asyncio
async def test_non_monday_uses_news_hook_draft(test_db):
    """On any other day, the pipeline must keep using the existing news-hook generator."""
    user_id = await _seed_user(test_db)
    tuesday = date(2026, 9, 15)
    assert tuesday.weekday() == 1

    patches = _patch_common(tuesday)
    with patch(
        "app.services.scheduler_service.generate_monday_project_spotlight",
        AsyncMock(return_value="spotlight draft"),
    ) as mock_spotlight, patch(
        "app.services.scheduler_service.generate_draft", AsyncMock(return_value="news draft")
    ) as mock_news_draft:
        for p in patches:
            p.start()
        try:
            result = await run_daily_pipeline(user_id=user_id, db=test_db, settings=_settings(), run_type="manual")
        finally:
            for p in patches:
                p.stop()

    assert result["status"] == "success"
    mock_news_draft.assert_awaited_once()
    mock_spotlight.assert_not_awaited()
