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
@patch("app.services.summarizer_service.call_llm_with_fallback")
async def test_monday_project_spotlight_stateful_rotation(mock_llm, test_db):
    """Test stateful rotation of Monday projects and prevention of back-to-back repeats on cycle reset."""
    from app.models.showcased_project import ShowcasedProject
    from sqlalchemy import select

    mock_llm.return_value = "Mocked project spotlight draft content"

    settings = Settings(
        secret_key="test",
        linkedin_client_id="id",
        linkedin_client_secret="sec",
        openai_api_key="key",
        fernet_key="On9Xt3DeuvikAzn4c-yVjMCAyVAJJXGvKAh6rOstuUU=",
    )

    repos = [
        {"name": "repoA", "html_url": "http://gh/repoA", "description": "Desc A", "language": "Python"},
        {"name": "repoB", "html_url": "http://gh/repoB", "description": "Desc B", "language": "Python"},
        {"name": "repoC", "html_url": "http://gh/repoC", "description": "Desc C", "language": "Python"},
    ]

    # Clear showcased projects first for test isolation
    from sqlalchemy import delete
    await test_db.execute(delete(ShowcasedProject))
    await test_db.commit()

    # 1st week: repoA should be chosen (first of the unshowcased, star-sorted list)
    with patch("app.services.summarizer_service.get_resume_context", return_value="Resume"), \
         patch("os.path.exists", return_value=False):
        draft = await generate_monday_project_spotlight(repos, settings, db=test_db)
        assert draft == "Mocked project spotlight draft content"

        # Verify repoA in db
        stmt = select(ShowcasedProject.project_name)
        res = await test_db.execute(stmt)
        names = res.scalars().all()
        assert "repoA" in names
        assert len(names) == 1

        # 2nd week: repoB should be chosen
        await generate_monday_project_spotlight(repos, settings, db=test_db)
        res = await test_db.execute(stmt)
        names = res.scalars().all()
        assert "repoB" in names
        assert len(names) == 2

        # 3rd week: repoC should be chosen
        await generate_monday_project_spotlight(repos, settings, db=test_db)
        res = await test_db.execute(stmt)
        names = res.scalars().all()
        assert "repoC" in names
        assert len(names) == 3

        # 4th week: all are showcased. Cycle reset should trigger.
        # repoC was the last showcased, so the reset pool will exclude repoC.
        # Since the pool is [repoA, repoB], it will choose repoA (first element of the pool).
        await generate_monday_project_spotlight(repos, settings, db=test_db)
        res = await test_db.execute(stmt)
        names = res.scalars().all()

        # Verify that repoC is NOT in the database (since we reset, and we picked repoA, so only repoA is now in showcased list)
        assert "repoA" in names
        assert "repoC" not in names
        assert len(names) == 1

