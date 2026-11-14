"""Tests for drafting: the weekly schedule, the prompt's rules, and the draft/check/rewrite loop."""

from datetime import date
from unittest.mock import AsyncMock, patch

from tests.fillers import filler as filler_words
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


GOOD = ("I wrote 15 dbt tests before trusting a single number from the warehouse.\n\n" + "The Job Search dbt Warehouse is a dimensional dbt model on Databricks. " + filler_words()
        + "\n\nI am open to Data Engineer and Machine Learning Engineer roles.\n\n"
        "If you model a warehouse in dbt, how many tests do you write before trusting a number?\n\n#dbt #DataEngineering")


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


@pytest.mark.asyncio
async def test_the_fact_check_also_reports_where_the_reading_flow_drops():
    async def llm(messages, settings, temperature, tier="any"):
        return '{"unsupported": [], "flow": ["paragraph 3 jumps to the test without saying why it was needed"]}'

    with patch.object(ss, "call_llm_with_fallback", llm):
        problems = await ss.critic_problems("post", "facts", object())
    assert problems == ["reading flow: paragraph 3 jumps to the test without saying why it was needed"]


def test_approved_posts_become_examples():
    from app.services.summarizer_service import approved_examples

    queue = [{"subject": "Other", "text": "x"}, {"subject": "Land Use", "text": "LAND"}, {"subject": "Lakehouse", "text": "LAKE"}]
    import app.services.post_rules as rules

    real = rules.writing_problems
    rules.writing_problems = lambda text, source_text="", exempt=frozenset(): []
    try:
        out = approved_examples("Lakehouse", queue)
    finally:
        rules.writing_problems = real
    assert "LAND" in out and "LAKE" not in out


def test_real_queue_gives_at_least_two_examples():
    import json

    from app.services.summarizer_service import APPROVED_EXAMPLES, approved_examples

    queue = json.load(open("data/approved_queue.json", encoding="utf-8"))
    out = approved_examples("FinTech Credit Risk & Fraud Command Center", queue)
    assert out != APPROVED_EXAMPLES and out.count("--- APPROVED POST") >= 2


BARE = "opening: the first paragraph is a bare result; say first what the project is and what problem it solves, then the result"
SETTING = "The Job Search dbt Warehouse is my dbt project for checking warehouse numbers before anyone relies on them."


def _bare_unless_set(text, *a, **k):
    return [] if text.startswith("The Job Search dbt Warehouse is my") else [BARE]


@pytest.mark.asyncio
async def test_a_bare_result_opening_gets_a_setting_sentence_instead_of_another_full_rewrite():
    prompts = []

    async def llm(messages, settings, temperature, tier="any"):
        content = messages[0]["content"]
        prompts.append(content)
        if "Write ONE sentence to go before that opening line" in content:
            return SETTING
        if "checking a LinkedIn post" in content:
            return '{"unsupported": []}'
        return GOOD

    with patch.object(ss, "call_llm_with_fallback", llm), patch.object(ss, "pick_subject", lambda *a: _item("Job Search dbt")), \
            patch.object(ss, "check_draft", _bare_unless_set):
        result = await ss.generate_post("project_spotlight", SAMPLE_PROFILE, object(), date(2026, 11, 16), [], [])
    assert result["text"].startswith(SETTING + "\n\n" + GOOD.split("\n\n")[0] + " " + GOOD.split("\n\n")[1])
    assert result["text"].split("\n\n")[2:] == GOOD.split("\n\n")[2:]  # the rest of the post is unchanged


@pytest.mark.asyncio
async def test_a_labelled_setting_reply_is_cleaned_to_its_sentence():
    async def llm(messages, settings, temperature, tier="any"):
        content = messages[0]["content"]
        if "Write ONE sentence to go before that opening line" in content:
            return "Sentence: " + SETTING + " It also runs in CI.\n\n(This keeps the result.)"
        if "checking a LinkedIn post" in content:
            return '{"unsupported": []}'
        return GOOD

    with patch.object(ss, "call_llm_with_fallback", llm), patch.object(ss, "pick_subject", lambda *a: _item("Job Search dbt")),             patch.object(ss, "check_draft", _bare_unless_set):
        result = await ss.generate_post("project_spotlight", SAMPLE_PROFILE, object(), date(2026, 11, 16), [], [])
    assert result["text"].startswith(SETTING + "\n\nI wrote 15 dbt tests")


@pytest.mark.asyncio
async def test_an_unusable_setting_reply_leaves_the_draft_rejected():
    async def llm(messages, settings, temperature, tier="any"):
        if "Write ONE sentence to go before that opening line" in messages[0]["content"]:
            return "OK."
        return GOOD

    with patch.object(ss, "call_llm_with_fallback", llm), patch.object(ss, "pick_subject", lambda *a: _item("Job Search dbt")),             patch.object(ss, "check_draft", _bare_unless_set):
        with pytest.raises(ss.DraftRejected) as exc:
            await ss.generate_post("project_spotlight", SAMPLE_PROFILE, object(), date(2026, 11, 16), [], [])
    assert exc.value.problems == [BARE]


@pytest.mark.asyncio
async def test_the_opening_is_fixed_even_when_the_draft_has_other_problems_and_the_sentence_is_reused():
    calls = {"setting": 0, "rewrite": 0}

    def check(text, *a, **k):
        found = [] if text.startswith("The Job Search dbt Warehouse is my") else [BARE]
        return found + (["closing: too general"] if "MARK" in text else [])

    async def llm(messages, settings, temperature, tier="any"):
        content = messages[0]["content"]
        if "Write ONE sentence to go before that opening line" in content:
            calls["setting"] += 1
            return SETTING
        if "checking a LinkedIn post" in content:
            return '{"unsupported": []}'
        if "Your previous draft is below" in content:
            calls["rewrite"] += 1
            return GOOD  # the rewrite fixes the closing but opens on the bare result again
        return GOOD.replace("#dbt", "MARK #dbt")

    with patch.object(ss, "call_llm_with_fallback", llm), patch.object(ss, "pick_subject", lambda *a: _item("Job Search dbt")), \
            patch.object(ss, "check_draft", check):
        result = await ss.generate_post("project_spotlight", SAMPLE_PROFILE, object(), date(2026, 11, 16), [], [])
    assert result["text"].startswith(SETTING) and "MARK" not in result["text"]
    assert calls == {"setting": 1, "rewrite": 1}


@pytest.mark.asyncio
async def test_a_flagged_paraphrase_is_dropped_only_when_its_passage_is_really_in_the_facts():
    facts = "Detail: The gain comes from promotion weeks, which last week's sales cannot anticipate."
    flagged = '{"unsupported": ["model anticipated promotion weeks", "report is for anyone who follows the market"], "flow": []}'
    recheck = ('{"checks": [{"claim": "model anticipated promotion weeks", "passage": "The gain comes from promotion weeks, which '
               'last week’s sales cannot anticipate"}, {"claim": "report is for anyone", "passage": "The report is read by '
               'market followers every day"}]}')
    replies = iter([flagged, recheck])

    async def llm(messages, settings, temperature, tier="any"):
        return next(replies)

    with patch.object(ss, "call_llm_with_fallback", llm):
        problems = await ss.critic_problems("post", facts, object())
    assert problems == ["unsupported by the facts: report is for anyone who follows the market"]


@pytest.mark.asyncio
async def test_findings_stand_when_the_recheck_fails():
    replies = iter(['{"unsupported": ["invented feature"], "flow": []}', "not json"])

    async def llm(messages, settings, temperature, tier="any"):
        return next(replies)

    with patch.object(ss, "call_llm_with_fallback", llm):
        problems = await ss.critic_problems("post", "facts", object())
    assert problems == ["unsupported by the facts: invented feature"]
