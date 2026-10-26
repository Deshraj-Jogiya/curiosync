"""Approved posts go out word for word before any new draft is written, in queue order, each once."""

import json
from datetime import date
from unittest.mock import AsyncMock

import pytest

from app.services.approved_queue import load_queue, next_approved


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


def test_next_draft_fills_the_first_post_day_not_taken_by_an_approved_post(tmp_path, monkeypatch):
    from app.services.approved_queue import slot_for_next_draft

    _queue(tmp_path, monkeypatch)  # two approved posts waiting
    assert slot_for_next_draft(date(2026, 10, 25), []) == date(2026, 10, 30)  # Sun: Mon + Wed taken -> Fri
    assert slot_for_next_draft(date(2026, 10, 26), [{"date": "2026-10-26", "approved_id": "a"}]) == date(2026, 10, 30)  # A posted Mon, B takes Wed


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
