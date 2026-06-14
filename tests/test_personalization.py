"""Tests for GitHub service, resume service, and personalized draft generation."""

from unittest.mock import AsyncMock, patch, MagicMock
import pytest
from datetime import date
from app.config import Settings
from app.services.github_service import fetch_github_projects
from app.services.resume_service import get_resume_context
from app.services.summarizer_service import (
    generate_draft,
    generate_monday_project_spotlight,
)
from app.services.scheduler_service import run_daily_pipeline


@pytest.mark.asyncio
async def test_fetch_github_projects_no_username():
    """Verify that empty or default username returns an empty list immediately."""
    res = await fetch_github_projects("")
    assert res == []
    res2 = await fetch_github_projects("your-github-username")
    assert res2 == []


@pytest.mark.asyncio
@patch("httpx.AsyncClient.get")
async def test_fetch_github_projects_success(mock_get):
    """Test successful fetching and filtering of repositories."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {
            "name": "my-forked-repo",
            "fork": True,
            "html_url": "http://github.com/test/my-forked-repo",
            "language": "Python",
            "stargazers_count": 100,
            "topics": ["ai"],
        },
        {
            "name": "cool-project",
            "fork": False,
            "html_url": "http://github.com/test/cool-project",
            "language": "Python",
            "stargazers_count": 10,
            "topics": ["ml", "nlp"],
        },
        {
            "name": "awesome-project",
            "fork": False,
            "html_url": "http://github.com/test/awesome-project",
            "language": "TypeScript",
            "stargazers_count": 25,
            "topics": ["web"],
        },
    ]
    mock_get.return_value = mock_response

    res = await fetch_github_projects("valid-username")
    # Forks should be filtered out, and list sorted by stargazers desc
    assert len(res) == 2
    assert res[0]["name"] == "awesome-project"  # 25 stars
    assert res[1]["name"] == "cool-project"  # 10 stars


def test_resume_context():
    """Verify get_resume_context formats text containing resume summary."""
    ctx = get_resume_context()
    assert "USER PROFILE SUMMARY:" in ctx
    assert "Objectways Technologies LLC" in ctx
    assert "Arizona State University" in ctx


@pytest.mark.asyncio
@patch("openai.AsyncOpenAI")
async def test_generate_monday_project_spotlight_github(mock_async_openai):
    """Verify that spotlight post is correctly generated using GitHub projects."""
    mock_client = MagicMock()
    mock_create = AsyncMock()

    mock_choice = MagicMock()
    mock_choice.message.content = (
        "This is an awesome Monday Project Spotlight post!"
    )
    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_create.return_value = mock_response

    mock_client.chat.completions.create = mock_create
    mock_async_openai.return_value = mock_client

    settings = Settings(
        secret_key="test",
        linkedin_client_id="id",
        linkedin_client_secret="sec",
        openai_api_key="key",
        fernet_key="On9Xt3DeuvikAzn4c-yVjMCAyVAJJXGvKAh6rOstuUU=",
    )
    repos = [
        {
            "name": "repo1",
            "html_url": "http://gh/repo1",
            "description": "Desc",
            "language": "Python",
        }
    ]
    draft = await generate_monday_project_spotlight(repos, settings)
    assert draft == "This is an awesome Monday Project Spotlight post!"


@pytest.mark.asyncio
@patch("app.services.scheduler_service.today_phoenix")
@patch("app.services.scheduler_service.get_valid_token")
@patch("app.services.scheduler_service.fetch_github_projects")
@patch("app.services.scheduler_service.generate_monday_project_spotlight")
@patch("app.services.scheduler_service.publish_post")
async def test_scheduler_run_on_monday(
    mock_publish,
    mock_spotlight,
    mock_fetch_git,
    mock_token,
    mock_today,
    test_db,
):
    """Verify that on Monday, the daily pipeline runs the project spotlight flow."""
    # Mocking Monday: 2026-06-15 is a Monday (check: date(2026, 6, 15).weekday() == 0)
    mock_today.return_value = date(2026, 6, 15)
    mock_token.return_value = "mock_token"
    mock_fetch_git.return_value = [{"name": "test-repo"}]
    mock_spotlight.return_value = "This is the Monday project post"
    mock_publish.return_value = {
        "success": True,
        "post_id": "urn:li:share:12345",
    }

    # Insert a dummy user in db
    from app.models.user import User

    user = User(linkedin_sub="12345", name="Test User")
    test_db.add(user)
    await test_db.flush()

    settings = Settings(
        secret_key="test",
        linkedin_client_id="id",
        linkedin_client_secret="sec",
        openai_api_key="key",
        github_username="test_git",
        fernet_key="On9Xt3DeuvikAzn4c-yVjMCAyVAJJXGvKAh6rOstuUU=",
    )

    result = await run_daily_pipeline(
        user_id=user.id, db=test_db, settings=settings
    )
    assert result["status"] == "success"
    assert "github_fetch" in result["steps"]
    assert "generate_draft" in result["steps"]
    assert "news" not in result["steps"].get("fetch_news", "")
