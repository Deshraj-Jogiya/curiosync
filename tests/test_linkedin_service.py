"""Tests for the LinkedIn service."""

from unittest.mock import AsyncMock, patch, MagicMock
from datetime import date

import pytest
import pytest_asyncio

from app.services.linkedin_service import publish_post, check_duplicate_post
from app.models.post_history import PostHistory


class TestPublishPost:
    @pytest.mark.asyncio
    async def test_successful_publish(self):
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.headers = {"x-restli-id": "urn:li:share:123456"}

        settings = MagicMock()
        settings.linkedin_posts_url = "https://api.linkedin.com/rest/posts"

        with patch("app.services.linkedin_service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await publish_post("token123", "urn:li:person:abc", "Test post", settings)

        assert result["success"] is True
        assert result["post_id"] == "urn:li:share:123456"
        assert result["error"] is None

    @pytest.mark.asyncio
    async def test_auth_error_401(self):
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        settings = MagicMock()
        settings.linkedin_posts_url = "https://api.linkedin.com/rest/posts"

        with patch("app.services.linkedin_service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await publish_post("bad_token", "urn:li:person:abc", "Test post", settings)

        assert result["success"] is False
        assert "401" in result["error"]

    @pytest.mark.asyncio
    async def test_rate_limit_429(self):
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = "Rate limited"

        settings = MagicMock()
        settings.linkedin_posts_url = "https://api.linkedin.com/rest/posts"

        with patch("app.services.linkedin_service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await publish_post("token", "urn:li:person:abc", "Test post", settings)

        assert result["success"] is False
        assert "rate" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        import httpx

        settings = MagicMock()
        settings.linkedin_posts_url = "https://api.linkedin.com/rest/posts"

        with patch("app.services.linkedin_service.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.side_effect = httpx.TimeoutException("timeout")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await publish_post("token", "urn:li:person:abc", "Test post", settings)

        assert result["success"] is False
        assert "timed out" in result["error"].lower()


class TestCheckDuplicatePost:
    @pytest.mark.asyncio
    async def test_no_duplicate(self, test_db):
        result = await check_duplicate_post(test_db, user_id=999, date_for=date.today())
        assert result is False

    @pytest.mark.asyncio
    async def test_duplicate_exists(self, test_db):
        post = PostHistory(
            user_id=1,
            draft_id=None,
            status="published",
            content="Test post",
            date_for=date.today(),
        )
        test_db.add(post)
        await test_db.flush()

        result = await check_duplicate_post(test_db, user_id=1, date_for=date.today())
        assert result is True
