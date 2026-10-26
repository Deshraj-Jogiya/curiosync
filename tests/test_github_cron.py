"""Tests for the standalone GitHub Actions runner (draft and publish modes)."""

import json
import os
from datetime import date, datetime, timedelta
from unittest.mock import AsyncMock, patch

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

    assert mock_pipeline.call_args.kwargs["user_id"] == user.id
    assert mock_pipeline.call_args.kwargs["draft_format"] in ("project_spotlight", "lesson", "decision")
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


def _pending(tmp_path, post_day="2026-10-30"):
    d = tmp_path / "pending_post"
    d.mkdir()
    (d / "post.txt").write_text("Approved post text", encoding="utf-8")
    (d / "image.png").write_bytes(b"\x89PNG fake")
    meta = {"created_at": datetime.utcnow().isoformat(), "format": "decision", "subject": "X", "alt_text": "Chart", "post_day": post_day,
            "history_entry": {"subject": "X", "format": "decision", "hook_type": "claim", "text": "Approved post text"}}
    (d / "meta.json").write_text(json.dumps(meta), encoding="utf-8")


def _queue(tmp_path, monkeypatch, items):
    path = tmp_path / "data" / "approved_queue.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(items), encoding="utf-8")
    monkeypatch.setattr("app.services.approved_queue.QUEUE_PATH", str(path))
    return path


def _day(monkeypatch, day):
    monkeypatch.setattr("app.utils.timezone.today_phoenix", lambda: day)


@pytest.mark.asyncio
@patch("app.services.linkedin_service.publish_post")
@patch("sys.exit")
async def test_approve_queues_the_draft_for_its_post_day_without_posting_early(mock_exit, mock_publish, tmp_path, monkeypatch):
    _pending(tmp_path)
    monkeypatch.chdir(tmp_path)
    path = _queue(tmp_path, monkeypatch, [])
    _day(monkeypatch, date(2026, 10, 27))  # Tuesday
    with patch.dict(os.environ, dict(ENV, GITHUB_RUN_ID="555")):
        await main("approve")
    queue = json.loads(path.read_text(encoding="utf-8"))
    assert queue[0]["id"] == "draft-555" and queue[0]["text"] == "Approved post text" and queue[0]["post_day"] == "2026-10-30"
    assert (tmp_path / "assets" / "approved" / "draft-555.png").exists()
    mock_publish.assert_not_called()
    mock_exit.assert_called_once_with(0)


@pytest.mark.asyncio
@patch("app.services.linkedin_service.publish_post")
@patch("sys.exit")
async def test_approving_on_its_post_day_posts_it_at_once(mock_exit, mock_publish, tmp_path, monkeypatch):
    mock_publish.return_value = {"success": True, "post_id": "1"}
    _pending(tmp_path, "2026-10-30")
    monkeypatch.chdir(tmp_path)
    _queue(tmp_path, monkeypatch, [])
    _day(monkeypatch, date(2026, 10, 30))  # Friday
    with patch.dict(os.environ, dict(ENV, GITHUB_RUN_ID="556")):
        await main("approve")
    assert mock_publish.call_args.args[1] == "urn:li:person:mock-sub-456"
    assert mock_publish.call_args.args[2] == "Approved post text"
    history = json.loads((tmp_path / "data" / "post_history.json").read_text(encoding="utf-8"))
    assert history[-1]["approved_id"] == "draft-556" and history[-1]["date"] == "2026-10-30"
    mock_exit.assert_called_once_with(0)


@pytest.mark.asyncio
@patch("github_cron.generate_and_save_til")
@patch("github_cron.run_daily_pipeline")
@patch("app.services.linkedin_service.publish_post")
@patch("sys.exit")
async def test_post_day_posts_the_approved_post_then_drafts_for_the_next_open_day(mock_exit, mock_publish, mock_pipeline, mock_til,
                                                                                   tmp_path, monkeypatch):
    mock_publish.return_value = {"success": True, "post_id": "1"}
    mock_pipeline.return_value = {"status": "drafted", "draft": "New", "format": "decision", "subject": "S", "image_path": None,
                                  "compliance": {"issues": []}, "steps": {}}
    monkeypatch.chdir(tmp_path)
    _queue(tmp_path, monkeypatch, [{"id": "a", "format": "lesson", "subject": "A", "text": "Post A."},
                                   {"id": "b", "format": "lesson", "subject": "B", "text": "Post B."}])
    _day(monkeypatch, date(2026, 10, 26))  # Monday
    out = tmp_path / "out.txt"
    with patch.dict(os.environ, dict(ENV, GITHUB_OUTPUT=str(out))):
        await main("draft")
    assert mock_publish.call_args.args[2] == "Post A."
    # Monday is taken by A (posted) and Wednesday by B, so the new draft is Friday's decision post.
    assert mock_pipeline.call_args.kwargs["draft_day"] == date(2026, 10, 30)
    assert mock_pipeline.call_args.kwargs["draft_format"] == "decision"
    assert [h["subject"] for h in mock_pipeline.call_args.kwargs["extra_history"]] == ["B"]
    assert json.loads((tmp_path / "pending_post" / "meta.json").read_text())["post_day"] == "2026-10-30"
    assert "has_draft=true" in out.read_text()
    mock_exit.assert_called_once_with(0)


@pytest.mark.asyncio
@patch("github_cron.generate_and_save_til")
@patch("github_cron.run_daily_pipeline")
@patch("app.services.linkedin_service.publish_post")
@patch("sys.exit")
async def test_no_new_draft_while_one_waits_for_approval_or_the_queue_is_full(mock_exit, mock_publish, mock_pipeline, mock_til,
                                                                               tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _day(monkeypatch, date(2026, 10, 27))  # Tuesday: nothing to post
    _queue(tmp_path, monkeypatch, [])
    with patch.dict(os.environ, dict(ENV, WAITING_APPROVALS="1")):
        await main("draft")
    _queue(tmp_path, monkeypatch, [{"id": i, "format": "lesson", "subject": i, "text": i} for i in "abc"])
    with patch.dict(os.environ, ENV):
        await main("draft")
    mock_pipeline.assert_not_called()
    mock_publish.assert_not_called()


@pytest.mark.asyncio
@patch("github_cron.generate_and_save_til")
@patch("github_cron.run_daily_pipeline")
@patch("sys.exit")
async def test_redraft_after_a_reject_does_not_write_a_second_til(mock_exit, mock_pipeline, mock_til, tmp_path, monkeypatch):
    mock_pipeline.return_value = {"status": "skipped", "steps": {}}
    monkeypatch.chdir(tmp_path)
    _day(monkeypatch, date(2026, 10, 27))
    _queue(tmp_path, monkeypatch, [])
    with patch.dict(os.environ, dict(ENV, REDRAFT="true")):
        await main("draft")
    assert mock_pipeline.call_args.kwargs["run_type"] == "redraft"
    mock_til.assert_not_called()


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
    out = review_summary(text, {"subject": "Project A", "warnings": [], "alt_text": "Chart of *things*", "post_day": "2026-10-30"},
                         "https://raw.githubusercontent.com/o/r/previews/1.png", "https://github.com/o/r/actions/runs/1")
    assert "Review deployments" in out and "Approve and deploy" in out and "Friday, October 30" in out and "Reject" in out
    assert "![Post image](https://raw.githubusercontent.com/o/r/previews/1.png)" in out
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
    _queue(tmp_path, monkeypatch, [])
    out = tmp_path / "out.txt"
    summary = tmp_path / "summary.md"
    monkeypatch.chdir(tmp_path)
    with patch.dict(os.environ, {**ENV, "PREVIEW_FORMAT": "lesson", "GITHUB_OUTPUT": str(out), "GITHUB_STEP_SUMMARY": str(summary)}):
        await main("draft")
    assert mock_pipeline.call_args.kwargs["draft_format"] == "lesson"
    outputs = out.read_text(encoding="utf-8")
    assert "has_draft=false" in outputs and "has_preview=true" in outputs
    assert "will not be posted" in summary.read_text(encoding="utf-8")
    mock_til.assert_not_called()


@pytest.mark.asyncio
@patch("github_cron.generate_and_save_til")
@patch("github_cron.run_daily_pipeline")
@patch("sys.exit")
async def test_a_document_draft_keeps_every_page_for_review_and_the_pdf(mock_exit, mock_pipeline, mock_til, tmp_path, monkeypatch):
    pages = []
    for n in range(1, 4):
        p = tmp_path / f"p{n}.png"
        p.write_bytes(b"\x89PNG page")
        pages.append(str(p))
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    mock_pipeline.return_value = {"status": "drafted", "draft": "Post", "format": "lesson", "subject": "S", "image_path": pages[0],
                                  "document_path": str(pdf), "document_pages": pages, "document_title": "Results",
                                  "compliance": {"issues": []}, "steps": {}}
    summary = tmp_path / "summary.md"
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)
    _queue(work, monkeypatch, [])
    _day(monkeypatch, date(2026, 10, 27))
    with patch.dict(os.environ, dict(ENV, GITHUB_STEP_SUMMARY=str(summary), GITHUB_REPOSITORY="o/r", GITHUB_RUN_ID="9")):
        await main("draft")
    assert sorted(os.listdir(work / "pending_post" / "pages")) == ["page-1.png", "page-2.png", "page-3.png"]
    assert (work / "pending_post" / "document.pdf").read_bytes() == b"%PDF-1.4"
    text = summary.read_text(encoding="utf-8")
    assert "3 pages" in text and "previews/9-p3.png" in text


@pytest.mark.asyncio
async def test_a_failed_media_upload_posts_nothing(tmp_path):
    from app.services.linkedin_service import publish_post

    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    with patch("app.services.linkedin_service._upload", AsyncMock(return_value=None)) as up, \
         patch("httpx.AsyncClient.post", AsyncMock()) as post:
        with patch.dict(os.environ, ENV):
            result = await publish_post("t", "urn:li:person:x", "text", get_settings(), document_path=str(pdf), document_title="R")
    assert result["success"] is False and "nothing was posted" in result["error"]
    up.assert_awaited_once()
    post.assert_not_called()
