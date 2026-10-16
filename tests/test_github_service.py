"""Tests for the GitHub service."""

from unittest.mock import AsyncMock, patch, MagicMock
import pytest
from app.services.github_service import fetch_github_projects


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


@pytest.mark.asyncio
@patch("httpx.AsyncClient.get")
async def test_fetch_github_projects_excludes_confidential_team_repos(mock_get):
    """Team-authored repos must never reach the Monday spotlight's candidate pool.

    generate_monday_project_spotlight frames whatever it picks as "your technical
    projects... your implementation details" -- so a real public repo for team work
    (Chef-at-Gathering, Stay-Aware-of-Branch, Get-Your-Token, City-Forums,
    Make-it-Short) must never be returned here, the same exclusion already applied
    to RESUME_DATA["projects"].
    """
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {
            "name": "Chef-at-Gathering",
            "fork": False,
            "html_url": "http://github.com/test/Chef-at-Gathering",
            "stargazers_count": 50,
        },
        {
            "name": "City-Forums",
            "fork": False,
            "html_url": "http://github.com/test/City-Forums",
            "stargazers_count": 40,
        },
        {
            "name": "Get-Your-Token",
            "fork": False,
            "html_url": "http://github.com/test/Get-Your-Token",
            "stargazers_count": 5,
        },
        {
            "name": "Make-it-Short",
            "fork": False,
            "html_url": "http://github.com/test/Make-it-Short",
            "stargazers_count": 3,
        },
        {
            "name": "Stay-Aware-of-Branch",
            "fork": False,
            "html_url": "http://github.com/test/Stay-Aware-of-Branch",
            "stargazers_count": 1,
        },
        {
            "name": "job-search-crm-automation",
            "fork": False,
            "html_url": "http://github.com/test/job-search-crm-automation",
            "stargazers_count": 2,
        },
    ]
    mock_get.return_value = mock_response

    res = await fetch_github_projects("valid-username")

    names = {r["name"] for r in res}
    assert names == {"job-search-crm-automation"}
