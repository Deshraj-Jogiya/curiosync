"""Tests for the standalone GitHub Actions runner (draft and publish modes)."""

import json
import os
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.database import async_session
from app.models.token import OAuthToken
from app.models.user import User
from github_cron import main

ENV = {
    "LINKEDIN_ACCESS_TOKEN": "mock-access-token-123",
    "LINKEDIN_SUB_URN": "urn:li:person:mock-sub-456",
    "OPENAI_API_KEY": "mock-openai-key",
    "SECRET_KEY": "test-secret",
    "LINKEDIN_CLIENT_ID": "test-id",
    "LINKEDIN_CLIENT_SECRET": "test-secret",
    "FERNET_KEY": "On9Xt3DeuvikAzn4c-yVjMCAyVAJJXGvKAh6rOstuUU=",
    "DATABASE_URL": "sqlite+aiosqlite:///:memory:",
}


@pytest.mark.asyncio
@patch("github_cron.generate_and_save_til")
@patch("github_cron.run_daily_pipeline")
@patch("sys.exit")
async def test_draft_mode_seeds_database_and_runs_pipeline(mock_exit, mock_pipeline, mock_til, tmp_path, monkeypatch):
    mock_pipeline.return_value = {"status": "skipped", "steps": {"schedule": "no post scheduled"}}
    monkeypatch.chdir(tmp_path)

    with patch.dict(os.environ, ENV):
        await main("draft")
        settings = get_settings()

    mock_exit.assert_called_once_with(0)
    async with async_session() as session:
        user = (await session.execute(select(User).where(User.linkedin_sub == "mock-sub-456"))).scalar_one_or_none()
        assert user is not None
        token = (await session.execute(select(OAuthToken).where(OAuthToken.user_id == user.id))).scalar_one_or_none()
        assert token is not None

    mock_pipeline.assert_called_once_with(user_id=user.id, run_type="github_actions_cron")
    assert token.decrypt_access_token(settings.fernet_key) == "mock-access-token-123"
    mock_til.assert_awaited_once()


@pytest.mark.asyncio
@patch("github_cron.generate_and_save_til")
@patch("github_cron.run_daily_pipeline")
@patch("sys.exit")
async def test_draft_mode_failure_exits_1(mock_exit, mock_pipeline, mock_til, tmp_path, monkeypatch):
    mock_pipeline.return_value = {"status": "failed", "error": "API error", "steps": {"some_step": "failed"}}
    monkeypatch.chdir(tmp_path)
    with patch.dict(os.environ, ENV):
        await main("draft")
    mock_exit.assert_called_once_with(1)
    mock_til.assert_awaited_once()  # the TIL note is still written when the post fails


@pytest.mark.asyncio
@patch("sys.exit")
async def test_missing_env_exits_1(mock_exit):
    with patch.dict(os.environ, dict(ENV, LINKEDIN_ACCESS_TOKEN="")):
        await main("draft")
    mock_exit.assert_called_once_with(1)


@pytest.mark.asyncio
@patch("github_cron.generate_and_save_til")
@patch("github_cron.run_daily_pipeline")
@patch("sys.exit")
async def test_draft_mode_saves_pending_post_and_summary(mock_exit, mock_pipeline, mock_til, tmp_path, monkeypatch):
    mock_pipeline.return_value = {"status": "drafted", "draft": "Draft body", "format": "lesson", "subject": "X",
                                  "image_path": None, "compliance": {"issues": ["Too short"]}, "steps": {}}
    out, summary = tmp_path / "out.txt", tmp_path / "summary.md"
    monkeypatch.chdir(tmp_path)
    with patch.dict(os.environ, dict(ENV, GITHUB_OUTPUT=str(out), GITHUB_STEP_SUMMARY=str(summary))):
        await main("draft")
    assert (tmp_path / "pending_post" / "post.txt").read_text(encoding="utf-8") == "Draft body"
    assert "has_draft=true" in out.read_text()
    text = summary.read_text(encoding="utf-8")
    assert "Draft body" in text and "Too short" in text
    mock_exit.assert_called_once_with(0)


def _pending(tmp_path, age_hours):
    d = tmp_path / "pending_post"
    d.mkdir()
    (d / "post.txt").write_text("Approved post text", encoding="utf-8")
    created = (datetime.utcnow() - timedelta(hours=age_hours)).isoformat()
    (d / "meta.json").write_text(json.dumps({"created_at": created, "format": "lesson", "subject": "X"}), encoding="utf-8")


@pytest.mark.asyncio
@patch("app.services.linkedin_service.publish_post")
@patch("sys.exit")
async def test_publish_posts_saved_draft_unchanged(mock_exit, mock_publish, tmp_path, monkeypatch):
    mock_publish.return_value = {"success": True, "post_id": "1"}
    _pending(tmp_path, 1)
    monkeypatch.chdir(tmp_path)
    with patch.dict(os.environ, ENV):
        await main("publish")
    assert mock_publish.call_args.args[1] == "urn:li:person:mock-sub-456"
    assert mock_publish.call_args.args[2] == "Approved post text"
    mock_exit.assert_called_once_with(0)


@pytest.mark.asyncio
@patch("app.services.linkedin_service.publish_post")
@patch("sys.exit")
async def test_publish_refuses_stale_draft(mock_exit, mock_publish, tmp_path, monkeypatch):
    _pending(tmp_path, 48)
    monkeypatch.chdir(tmp_path)
    with patch.dict(os.environ, ENV):
        await main("publish")
    mock_publish.assert_not_called()
    mock_exit.assert_called_once_with(0)


@pytest.mark.asyncio
@patch("github_cron.generate_and_save_til")
@patch("github_cron.run_daily_pipeline")
@patch("sys.exit")
async def test_expired_linkedin_token_fails_the_draft_run_but_still_writes_til(mock_exit, mock_pipeline, mock_til, tmp_path, monkeypatch):
    async def expired(_token):
        return False, "expired or revoked (401)"
    monkeypatch.setattr("github_cron.check_linkedin_token", expired)
    monkeypatch.chdir(tmp_path)
    with patch.dict(os.environ, ENV):
        await main("draft")
    mock_pipeline.assert_not_called()
    mock_til.assert_awaited()
    mock_exit.assert_called_with(1)
    assert "expired or revoked" in (tmp_path / "run_log.md").read_text(encoding="utf-8")


def test_review_summary_reads_like_the_post():
    from github_cron import review_summary

    text = "First line with 92.5% and a_b.\n\n- one point\n\n#DataEngineering #NLP"
    out = review_summary(text, {"subject": "Project A", "warnings": [], "alt_text": "Chart of *things*"},
                         "https://raw.githubusercontent.com/o/r/previews/1.png", "https://github.com/o/r/actions/runs/1")
    assert "Review deployments" in out and "Approve and deploy" in out
    assert '<img src="https://raw.githubusercontent.com/o/r/previews/1.png"' in out
    assert "\#DataEngineering" in out  # not turned into a heading
    assert "a\_b" in out and "- one point" in out
    assert "```text\n" + text + "\n```" in out  # exact copy kept


@pytest.mark.asyncio
@patch("github_cron.generate_and_save_til")
@patch("github_cron.run_daily_pipeline")
@patch("sys.exit")
async def test_preview_drafts_a_new_post_and_never_offers_it_for_publishing(mock_exit, mock_pipeline, mock_til, tmp_path, monkeypatch):
    mock_pipeline.return_value = {"status": "drafted", "draft": "New draft.", "format": "lesson", "subject": "S", "image_path": None,
                                  "compliance": {"issues": []}, "steps": {}}
    out = tmp_path / "out.txt"
    summary = tmp_path / "summary.md"
    monkeypatch.chdir(tmp_path)
    with patch.dict(os.environ, {**ENV, "PREVIEW_FORMAT": "lesson", "GITHUB_OUTPUT": str(out), "GITHUB_STEP_SUMMARY": str(summary)}):
        await main("draft")
    assert mock_pipeline.call_args.kwargs["preview_format"] == "lesson"
    outputs = out.read_text(encoding="utf-8")
    assert "has_draft=false" in outputs and "has_preview=true" in outputs
    assert "will not be posted" in summary.read_text(encoding="utf-8")
    mock_til.assert_not_called()
