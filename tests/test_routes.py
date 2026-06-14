"""Tests for FastAPI routes."""

import os
from unittest.mock import patch, MagicMock, AsyncMock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a test client with mocked settings."""
    env = {
        "SECRET_KEY": "test-secret-key-at-least-32-characters-long",
        "LINKEDIN_CLIENT_ID": "test-client-id",
        "LINKEDIN_CLIENT_SECRET": "test-client-secret",
        "LINKEDIN_REDIRECT_URI": "http://localhost:8000/auth/linkedin/callback",
        "OPENAI_API_KEY": "sk-test-key",
        "FERNET_KEY": "dGVzdC1mZXJuZXQta2V5LXRoYXQtaXMtbG9uZw==",
        "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
    }
    with patch.dict(os.environ, env):
        with patch("app.scheduler.start_scheduler"):
            with patch("app.scheduler.configure_scheduler"):
                # Force re-import with test settings
                import importlib
                import app.config
                importlib.reload(app.config)

                from app.main import create_app
                test_app = create_app()
                with TestClient(test_app, raise_server_exceptions=False) as c:
                    yield c


class TestPageRoutes:
    def test_root_shows_login_when_unauthenticated(self, client):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_login_page_loads(self, client):
        resp = client.get("/login")
        assert resp.status_code == 200


class TestAuthRoutes:
    def test_linkedin_login_redirects(self, client):
        resp = client.get("/auth/linkedin/login", follow_redirects=False)
        assert resp.status_code in (302, 307)
        location = resp.headers.get("location", "")
        assert "linkedin.com" in location

    def test_callback_with_error_redirects(self, client):
        resp = client.get(
            "/auth/linkedin/callback?error=access_denied&error_description=denied",
            follow_redirects=False,
        )
        assert resp.status_code in (302, 303, 307)
