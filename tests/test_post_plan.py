"""Tests for subject and hook selection."""

from datetime import date

from app.services import post_plan
from tests.sample_profile import SAMPLE_PROFILE

NOTES = {"_settings": {"min_year": 2024}, "CurioSync": {"exclude": True},
         "Job Market Lakehouse": {"simulated": True, "notes": ["I built it to learn."]}}
TODAY = date(2026, 10, 26)


def _titles(fmt, history=()):
    pool = post_plan.candidates(SAMPLE_PROFILE, "project", NOTES)
    return [i["title"] for i in pool], post_plan.pick_subject(SAMPLE_PROFILE, fmt, list(history), TODAY, NOTES)["title"]


def test_excluded_team_and_old_projects_never_picked():
    titles, _ = _titles("project_spotlight")
    assert not any(t.startswith(("CurioSync", "Chef at Gathering", "Old Project")) for t in titles)


def test_recently_posted_subject_is_skipped():
    _, first = _titles("project_spotlight")
    _, second = _titles("project_spotlight", [{"subject": first}])
    assert second != first


def test_simulated_flag_and_notes_come_from_the_notes_file():
    item = next(i for i in post_plan.candidates(SAMPLE_PROFILE, "project", NOTES) if i["title"] == "Job Market Lakehouse")
    assert item["simulated"] is True and item["notes"] == ["I built it to learn."]


def test_decision_prefers_subjects_with_owner_notes():
    assert post_plan.pick_subject(SAMPLE_PROFILE, "decision", [], TODAY, NOTES)["title"] == "Job Market Lakehouse"


def test_hooks_rotate_and_need_supporting_facts():
    item = {"facts": ["Wrote 15 dbt tests."], "notes": []}
    first = post_plan.pick_hook(item, [])
    second = post_plan.pick_hook(item, [{"hook_type": first}])
    assert first != second
    assert "bug_found" not in {post_plan.pick_hook(item, [{"hook_type": h} for h in post_plan.HOOK_TYPES][:k]) for k in range(6)}


def test_news_needs_a_tool_the_subject_used_and_is_rare():
    item = {"facts": ["Built dbt models on Databricks."]}
    news = [{"title": "Snowflake raises prices", "summary": ""}, {"title": "Databricks ships a new SQL warehouse", "summary": ""}]
    assert post_plan.matching_news(item, news)["title"].startswith("Databricks")
    assert post_plan.matching_news(item, news[:1]) is None
    assert post_plan.news_allowed([{"format": "lesson"}] * 5)
    assert not post_plan.news_allowed([{"format": "news_take"}, {"format": "lesson"}])


def test_history_round_trip(tmp_path):
    path = tmp_path / "data" / "post_history.json"
    post_plan.append_history({"subject": "A"}, str(path))
    post_plan.append_history({"subject": "B"}, str(path))
    import json
    assert [h["subject"] for h in json.loads(path.read_text())] == ["A", "B"]
