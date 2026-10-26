"""Tests for run_daily_pipeline: the weekly post schedule, profile loading, the draft-only default and blocking compliance."""

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


def _patch_common(day: date):
    """Patch every scheduler_service dependency except the ones a test overrides."""
    return [
        patch("app.services.scheduler_service.get_today_post", AsyncMock(return_value=None)),
        patch("app.services.scheduler_service.get_valid_token", AsyncMock(return_value="fake-token")),
        patch("app.services.scheduler_service.fetch_news", AsyncMock(return_value=[{"title": "x", "source_name": "y"}])),
        patch("app.services.scheduler_service.save_news_items", AsyncMock(return_value=None)),
        patch("app.services.scheduler_service.check_compliance", lambda text, items: {"passed": True, "issues": [], "blocking": []}),
        patch("app.services.scheduler_service.load_profile", AsyncMock(return_value={"title": "t"})),
        patch("app.services.scheduler_service.load_history", lambda: []),
        patch("app.services.scheduler_service.append_history", lambda entry: None),
        patch("app.services.scheduler_service.build_visual", AsyncMock(return_value=(None, None, "none"))),
        patch("app.services.scheduler_service.source_text", lambda *a: "facts"),
        patch("app.services.scheduler_service.publish_post", AsyncMock(return_value={"success": True, "post_id": "123"})),
        patch("app.services.scheduler_service.record_post", AsyncMock(return_value=None)),
        patch("app.services.scheduler_service.today_phoenix", lambda: day),
    ]


async def _run(test_db, day, publish=False, gen=None, **overrides):
    user_id = await _seed_user(test_db)
    gen = gen or AsyncMock(side_effect=lambda fmt, *a, **k: {"text": "draft text", "subject": "Some Project", "format": fmt,
                                                            "hook_type": "claim", "item": {}, "attempts": 4, "news": None})
    patches = _patch_common(day) + [patch("app.services.scheduler_service.generate_post", gen)]
    patches += [patch(f"app.services.scheduler_service.{k}", v) for k, v in overrides.items()]
    for p in patches:
        p.start()
    try:
        result = await run_daily_pipeline(user_id=user_id, db=test_db, settings=_settings(), run_type="manual", publish=publish)
    finally:
        for p in patches:
            p.stop()
    return result, gen


@pytest.mark.asyncio
async def test_monday_drafts_project_spotlight_without_publishing(test_db):
    result, gen = await _run(test_db, date(2026, 9, 14))
    assert result["status"] == "drafted"
    assert result["format"] == "project_spotlight"
    assert result["draft"] == "draft text"
    assert gen.await_args.args[0] == "project_spotlight"


@pytest.mark.asyncio
async def test_draft_mode_never_calls_linkedin(test_db):
    publish = AsyncMock(return_value={"success": True, "post_id": "1"})
    result, _ = await _run(test_db, date(2026, 9, 16), publish_post=publish)
    assert result["status"] == "drafted"
    publish.assert_not_awaited()


@pytest.mark.asyncio
async def test_wednesday_is_lesson_and_news_is_fetched_only_on_friday(test_db):
    fetch = AsyncMock(return_value=[{"title": "x", "source_name": "y"}])
    _, gen = await _run(test_db, date(2026, 9, 16), fetch_news=fetch)
    assert gen.await_args.args[0] == "lesson"
    fetch.assert_not_awaited()


@pytest.mark.asyncio
async def test_friday_is_decision_and_survives_a_news_outage(test_db):
    result, gen = await _run(test_db, date(2026, 9, 18), fetch_news=AsyncMock(side_effect=RuntimeError("feeds down")))
    assert gen.await_args.args[0] == "decision"
    assert result["status"] == "drafted"


@pytest.mark.asyncio
async def test_rejected_draft_skips_the_day(test_db):
    from app.services.summarizer_service import DraftRejected

    publish = AsyncMock()
    result, _ = await _run(test_db, date(2026, 9, 14), publish=True, gen=AsyncMock(side_effect=DraftRejected(["number '45%' is not in the facts"])),
                           publish_post=publish)
    assert result["status"] == "skipped"
    publish.assert_not_awaited()


@pytest.mark.asyncio
async def test_successful_publish_is_recorded_in_history(test_db):
    saved = []
    result, _ = await _run(test_db, date(2026, 9, 14), publish=True, append_history=saved.append)
    assert result["status"] == "success"
    assert saved and saved[0]["subject"] == "Some Project" and saved[0]["hook_type"] == "claim"


@pytest.mark.asyncio
async def test_off_day_drafts_nothing(test_db):
    gen = AsyncMock()
    result, _ = await _run(test_db, date(2026, 9, 15), gen=gen)  # a Tuesday
    assert result["status"] == "skipped"
    gen.assert_not_awaited()


@pytest.mark.asyncio
async def test_explicit_publish_posts(test_db):
    result, _ = await _run(test_db, date(2026, 9, 18), publish=True)
    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_profile_unavailable_fails_without_drafting(test_db):
    from app.services.profile_source import ProfileUnavailable

    gen = AsyncMock()
    result, _ = await _run(test_db, date(2026, 9, 14), gen=gen, load_profile=AsyncMock(side_effect=ProfileUnavailable("down")))
    assert result["status"] == "failed"
    gen.assert_not_awaited()


@pytest.mark.asyncio
async def test_blocking_compliance_issue_stops_the_draft(test_db):
    blocked = {"passed": False, "issues": ["x"], "blocking": ["Contains a link or domain name"]}
    result, _ = await _run(test_db, date(2026, 9, 14), check_compliance=lambda t, i: blocked)
    assert result["status"] == "failed"
    assert "blocked" in result["error"].lower()


@pytest.mark.asyncio
async def test_preview_drafts_the_chosen_format_on_any_day_and_skips_the_queue(test_db, tmp_path, monkeypatch):
    path = tmp_path / "q.json"
    path.write_text('[{"id": "a", "format": "lesson", "subject": "A", "text": "Approved."}]', encoding="utf-8")
    monkeypatch.setattr("app.services.approved_queue.QUEUE_PATH", str(path))
    user_id = await _seed_user(test_db)
    gen = AsyncMock(side_effect=lambda fmt, *a, **k: {"text": "new draft", "subject": "P", "format": fmt, "hook_type": "claim",
                                                      "item": {}, "attempts": 3, "news": None})
    patches = _patch_common(date(2026, 10, 25)) + [patch("app.services.scheduler_service.generate_post", gen)]
    for p in patches:
        p.start()
    try:
        result = await run_daily_pipeline(user_id=user_id, db=test_db, settings=_settings(), run_type="preview", preview_format="decision")
    finally:
        for p in patches:
            p.stop()
    assert result["status"] == "drafted" and result["draft"] == "new draft" and result["format"] == "decision"
