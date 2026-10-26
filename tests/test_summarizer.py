"""Tests for drafting: the weekly schedule, the prompt's rules, and the draft/check/rewrite loop."""

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from app.services import summarizer_service as ss
from app.services.post_plan import enrich
from app.services.profile_source import featurable_items
from tests.sample_profile import SAMPLE_PROFILE

NOTES = {"_settings": {"min_year": 2024}}


def _item(title_start: str, kind: str = "project") -> dict:
    return enrich(next(i for i in featurable_items(SAMPLE_PROFILE, kind) if i["title"].startswith(title_start)), NOTES)


class TestSchedule:
    def test_three_posts_a_week_and_no_news_slot(self):
        week = [ss.post_format_for(date(2026, 11, 16 + i)) for i in range(7)]  # Mon 16 Nov .. Sun 22 Nov
        assert week == ["project_spotlight", None, "lesson", None, "decision", None, None]

    def test_roles_from_title(self):
        assert ss.roles_from_title("Data Engineer & Machine Learning Engineer") == "Data Engineer and Machine Learning Engineer"


class TestPrompt:
    def test_solo_project_must_say_i(self):
        prompt = ss.build_prompt("project_spotlight", SAMPLE_PROFILE, _item("Job Search dbt"), "measured_result")
        assert "never 'we'" in prompt
        assert "Never call yourself senior" in prompt
        assert "No links" in prompt

    def test_simulated_project_must_say_so(self):
        prompt = ss.build_prompt("lesson", SAMPLE_PROFILE, _item("Job Market Lakehouse"), "claim")
        assert "simulated or synthetic data" in prompt

    def test_backstory_only_from_owner_notes(self):
        prompt = ss.build_prompt("lesson", SAMPLE_PROFILE, _item("Job Search dbt"), "claim")
        assert "may only come from YOUR OWN NOTES" in prompt
        assert "YOUR OWN NOTES:\n(empty)" in prompt

    def test_facts_and_focus(self):
        item = _item("Job Search dbt")
        prompt = ss.build_prompt("project_spotlight", SAMPLE_PROFILE, item, "measured_result")
        assert item["facts"][0] in prompt
        assert "at most three facts" in prompt
        assert "<strong>" not in prompt

    def test_news_only_when_given(self):
        item = _item("Job Search dbt")
        news = {"source_name": "dbt Labs", "title": "dbt adds a new test type", "summary": "s"}
        assert "NEWS:" in ss.build_prompt("news_take", SAMPLE_PROFILE, item, "claim", news)
        assert "NEWS:" not in ss.build_prompt("lesson", SAMPLE_PROFILE, item, "claim")


GOOD = ("I wrote 15 dbt tests before trusting a single number from the warehouse.\n\n" + "The project is a dimensional dbt model on Databricks. " * 20
        + "\n\nI am open to Data Engineer and Machine Learning Engineer roles.\n\n#dbt #DataEngineering")


@pytest.mark.asyncio
async def test_accepts_a_clean_draft():
    llm = AsyncMock(side_effect=[GOOD, GOOD, GOOD, '{"unsupported": []}'])
    with patch.object(ss, "call_llm_with_fallback", llm), patch.object(ss, "pick_subject", lambda *a: _item("Job Search dbt")):
        result = await ss.generate_post("project_spotlight", SAMPLE_PROFILE, object(), date(2026, 11, 16), [], [])
    assert result["subject"].startswith("Job Search dbt")
    assert result["text"].endswith("#dbt #DataEngineering")


@pytest.mark.asyncio
async def test_rewrites_then_gives_up_rather_than_posting_an_invented_number():
    bad = GOOD.replace("15 dbt tests", "40 dbt tests")
    llm = AsyncMock(return_value=bad)
    with patch.object(ss, "call_llm_with_fallback", llm), patch.object(ss, "pick_subject", lambda *a: _item("Job Search dbt")):
        with pytest.raises(ss.DraftRejected) as exc:
            await ss.generate_post("project_spotlight", SAMPLE_PROFILE, object(), date(2026, 11, 16), [], [])
    assert any("'40'" in p for p in exc.value.problems)
    assert llm.await_count == ss.DRAFTS_PER_RUN + ss.MAX_REWRITES


@pytest.mark.asyncio
async def test_fact_check_failure_rejects_the_draft():
    async def llm(messages, settings, temperature, tier="any"):
        if "checking a LinkedIn post" in messages[0]["content"]:
            raise RuntimeError("quota")
        return GOOD

    with patch.object(ss, "call_llm_with_fallback", llm), patch.object(ss, "pick_subject", lambda *a: _item("Job Search dbt")):
        with pytest.raises(ss.DraftRejected) as exc:
            await ss.generate_post("project_spotlight", SAMPLE_PROFILE, object(), date(2026, 11, 16), [], [])
    assert any("fact check could not run" in p for p in exc.value.problems)


@pytest.mark.asyncio
async def test_decision_without_owner_notes_becomes_a_lesson():
    llm = AsyncMock(side_effect=[GOOD, GOOD, GOOD, '{"unsupported": []}'])
    with patch.object(ss, "call_llm_with_fallback", llm), patch.object(ss, "pick_subject", lambda *a: _item("Job Search dbt")):
        result = await ss.generate_post("decision", SAMPLE_PROFILE, object(), date(2026, 11, 20), [], [])
    assert result["format"] == "lesson"
