"""Post measurements, the analytics-export import, the post-is-live alert and what publishing records."""

import json
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from app.services import post_alert
from app.services import post_metrics as pm

HISTORY = [{"date": f"2026-11-{d:02d}", "subject": f"P{d}", "text": f"Opening line number {d} of the post\n\nBody"}
           for d in (2, 4, 6, 9, 11)]


def test_record_stores_age_and_replaces_the_same_day():
    rows = []
    pm.record(rows, HISTORY[0], date(2026, 11, 9), 50)
    pm.record(rows, HISTORY[0], date(2026, 11, 9), 55)
    assert rows == [{"date": "2026-11-02", "measured_at": "2026-11-09", "age_days": 7, "impressions": 55, "reactions": None,
                     "comments": None, "reposts": None, "source": "manual"}]


def test_seven_day_prefers_the_reading_nearest_seven_days():
    rows = []
    pm.record(rows, HISTORY[0], date(2026, 11, 3), 20)   # 1 day: too young to compare
    pm.record(rows, HISTORY[0], date(2026, 11, 10), 60)  # 8 days
    pm.record(rows, HISTORY[0], date(2026, 11, 30), 70)  # 28 days
    assert pm.seven_day(rows, "2026-11-02")["impressions"] == 60
    rows2 = [r for r in rows if r["age_days"] != 8]
    assert pm.seven_day(rows2, "2026-11-02")["impressions"] == 70
    assert pm.seven_day([r for r in rows if r["age_days"] == 1], "2026-11-02") is None


def test_relative_reach_divides_by_the_median_of_earlier_posts():
    rows = []
    for h, n in zip(HISTORY, (100, 50, 80, 160, 40)):
        pm.record(rows, h, date.fromisoformat(h["date"]).replace(day=int(h["date"][-2:]) + 7), n)
    out = pm.relative_reach(rows, HISTORY)
    assert [o["ratio"] for o in out[:3]] == [None, None, None]
    assert out[3]["baseline"] == 80 and out[3]["ratio"] == 2.0
    assert out[4]["baseline"] == 90 and out[4]["ratio"] == 0.44


def test_import_export_matches_rows_by_date_and_reports_strangers(tmp_path):
    f = tmp_path / "export.csv"
    f.write_text("Top posts\n\nPost URL,Post publish date,Impressions,Reactions,Comments\n"
                 "https://x/1,11/04/2026,131,3,0\nhttps://x/2,11/05/2026,7,0,0\n", encoding="utf-8")
    rows = []
    n, notes = pm.import_export(str(f), HISTORY, rows, date(2026, 11, 12))
    assert n == 1 and rows[0]["date"] == "2026-11-04" and rows[0]["impressions"] == 131 and rows[0]["age_days"] == 8
    assert rows[0]["reactions"] == 3 and len(notes) == 1 and "no post matched" in notes[0]


def test_import_export_without_an_impressions_column_records_nothing(tmp_path):
    f = tmp_path / "x.csv"
    f.write_text("a,b\n1,2\n", encoding="utf-8")
    assert pm.import_export(str(f), HISTORY, [], date(2026, 11, 12))[0] == 0


def test_due_lists_posts_seven_to_ten_days_old_without_a_reading():
    assert [h["date"] for h in pm.due_for_measurement([], HISTORY, date(2026, 11, 13))] == ["2026-11-04", "2026-11-06"]


@pytest.mark.asyncio
async def test_alert_without_a_token_only_reports(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    assert "no alert" in await post_alert.post_is_live({"subject": "x"})


def test_alert_body_links_the_post_and_asks_for_real_replies(monkeypatch):
    monkeypatch.setenv("GITHUB_REPOSITORY_OWNER", "owner")
    body = post_alert._body({"subject": "Tax", "post_id": "urn:li:share:1", "text": "First line\n\nrest"})
    assert body.startswith("@owner") and "https://www.linkedin.com/feed/update/urn:li:share:1/" in body and "First line" in body


@pytest.mark.asyncio
async def test_publishing_records_post_id_time_media_and_trigger(tmp_path, monkeypatch):
    import github_cron

    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "post_history.json").write_text("[]", encoding="utf-8")
    monkeypatch.setenv("CURIOSYNC_TRIGGER", "publish_now")
    item = {"id": "q1", "text": "Hello there\n\nBody", "subject": "S", "format": "lesson", "image": None, "history_entry": {}}
    with patch("app.services.approved_queue.next_approved", return_value=item), \
            patch("app.services.approved_queue.image_copy", return_value=None), \
            patch("app.services.post_plan.HISTORY_PATH", str(tmp_path / "data" / "post_history.json"), create=True), \
            patch("app.services.summarizer_service.post_format_for", return_value="lesson"), \
            patch("app.services.linkedin_service.publish_post", AsyncMock(return_value={"success": True, "post_id": "urn:li:share:9"})), \
            patch("app.services.post_alert.post_is_live", AsyncMock(return_value="ok")) as alert:
        out = await github_cron.publish_due("tok", "sub", None)
    assert out == "posted q1"
    from app.services.post_plan import load_history

    entry = load_history()[-1]
    assert entry["post_id"] == "urn:li:share:9" and entry["media"] == "text" and entry["trigger"] == "publish_now"
    assert entry["posted_at"].endswith("+00:00")
    assert entry["factors"]["media"] == "text" and entry["factors"]["angle"] == "lesson" and entry["factors"]["slot"] in ("morning", "afternoon")
    alert.assert_awaited_once()


def test_factors_flag_a_level_that_runs_on_its_own_weekday_and_a_dominant_one():
    from app.services.post_factors import balance, tag

    assert tag({"media": "image", "format": "lesson", "hook_type": "claim", "posted_at": "2026-11-23T16:30:00+00:00"}) ==         {"media": "image", "angle": "lesson", "hook": "claim", "slot": "morning"}
    posts = [{"date": d, "format": f, "media": "image", "hook_type": "measured_result"} for d, f in
             (("2026-11-02", "project_spotlight"), ("2026-11-04", "lesson"), ("2026-11-06", "decision"), ("2026-11-09", "project_spotlight"),
              ("2026-11-11", "lesson"))]
    notes = balance(posts)
    assert any(n.startswith("angle: each level runs on its own weekday") for n in notes)
    assert any(n.startswith("media: 5 of 5") for n in notes) and any(n.startswith("hook: 5 of 5") for n in notes)
