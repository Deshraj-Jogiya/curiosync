"""Approved posts go out word for word before any new draft is written, in queue order, each once."""

import json
from datetime import date
from unittest.mock import AsyncMock

import pytest

from app.services.approved_queue import load_queue, next_approved
from tests.test_scheduler_service import _run


def _queue(tmp_path, monkeypatch, image=True):
    img = tmp_path / "card.png"
    img.write_bytes(b"\x89PNG fake")
    items = [
        {"id": "a", "format": "project_spotlight", "subject": "Project A", "text": "Approved post A.", "image": str(img) if image else None,
         "alt_text": "Chart A"},
        {"id": "b", "format": "lesson", "subject": "Project B", "text": "Approved post B.", "image": None, "alt_text": None},
    ]
    path = tmp_path / "queue.json"
    path.write_text(json.dumps(items), encoding="utf-8")
    monkeypatch.setattr("app.services.approved_queue.QUEUE_PATH", str(path))
    return img


def test_next_approved_skips_posts_already_in_history(tmp_path, monkeypatch):
    _queue(tmp_path, monkeypatch)
    assert next_approved([])["id"] == "a"
    assert next_approved([{"approved_id": "a"}])["id"] == "b"
    assert next_approved([{"text": "Approved post A."}, {"text": "Approved post B."}]) is None


@pytest.mark.asyncio
async def test_post_day_uses_the_queued_post_without_a_model_call(test_db, tmp_path, monkeypatch):
    img = _queue(tmp_path, monkeypatch)
    gen = AsyncMock()
    profile = AsyncMock()
    result, _ = await _run(test_db, date(2026, 10, 26), gen=gen, load_profile=profile)
    assert result["status"] == "drafted"
    assert result["draft"] == "Approved post A."
    assert result["alt_text"] == "Chart A"
    assert result["history_entry"]["approved_id"] == "a"
    assert result["image_path"] != str(img) and open(result["image_path"], "rb").read() == img.read_bytes()
    assert img.exists()
    gen.assert_not_awaited()
    profile.assert_not_awaited()


@pytest.mark.asyncio
async def test_non_post_days_ignore_the_queue(test_db, tmp_path, monkeypatch):
    _queue(tmp_path, monkeypatch)
    result, _ = await _run(test_db, date(2026, 10, 25))
    assert result["status"] == "skipped"


@pytest.mark.asyncio
async def test_empty_queue_falls_back_to_a_new_draft(test_db):
    result, gen = await _run(test_db, date(2026, 10, 26))
    assert result["draft"] == "draft text"
    gen.assert_awaited()


def test_repo_queue_is_valid_and_its_images_exist(monkeypatch):
    monkeypatch.setattr("app.services.approved_queue.QUEUE_PATH", "data/approved_queue.json")
    from app.services.compliance_service import check_compliance

    for item in load_queue():
        assert {"id", "format", "subject", "text"} <= item.keys()
        if item.get("image"):
            with open(item["image"], "rb") as f:
                assert f.read(4) == b"\x89PNG"
        assert not check_compliance(item["text"], [])["blocking"]
    ids = [i["id"] for i in load_queue()]
    assert len(ids) == len(set(ids))
