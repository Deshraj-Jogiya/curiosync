"""Stories: one measured test per post, every number from the project's own documents, and an image built from the same numbers."""

import json
from unittest.mock import AsyncMock, patch

import pytest
from PIL import Image

from app.services.post_visual import render_story_chart, story_results_in_post
from app.services.story_bank import add_feedback, load_stories, pick_story, refill, unused, verify_story

DOCS = """# Evaluation
We wrote 120 questions and held back 40. Keywords only answered 63% right; with the reranker it reached 83%, and the final
design reached 92.5% at 0.9 s per answer. We shipped the reranker version."""

STORY = {"id": "a-1", "subject": "Project A", "question": "Can it answer without an LLM?", "test": "40 held-out questions",
         "results": [{"label": "Keywords only", "value": "63%"}, {"label": "With reranker", "value": "83%"},
                     {"label": "Final design", "value": "92.5%"}],
         "decision": "Shipped the reranker version", "chart_title": "Held-out questions answered right", "detail": ""}

ITEMS = [{"kind": "project", "title": "Project A", "org": "", "dates": "2026", "facts": ["x"], "github_url": "https://github.com/o/a"},
         {"kind": "project", "title": "Project B", "org": "", "dates": "2025", "facts": ["y"], "github_url": "https://github.com/o/b"}]


def test_a_story_with_a_number_not_in_the_documents_is_dropped():
    assert verify_story(STORY, DOCS) == []
    bad = {**STORY, "results": STORY["results"] + [{"label": "Users", "value": "5,000"}]}
    assert any("not in the documents" in p for p in verify_story(bad, DOCS))
    assert "fewer than 3 numeric results" in verify_story({**STORY, "results": STORY["results"][:2]}, DOCS)
    same = {**STORY, "results": [{"label": "A", "value": "63%"}, {"label": "B", "value": "63%"}, {"label": "C", "value": "63%"}]}
    assert any("same number" in p for p in verify_story(same, DOCS))


def test_stories_are_used_once_and_dropped_after_two_rejects():
    b = {**STORY, "id": "b-1", "subject": "Project B"}
    assert pick_story(ITEMS, [], [STORY, b], [])[0]["id"] == "a-1"
    # Project A was posted about most recently, so B's story comes first.
    assert pick_story(ITEMS, [{"subject": "Project A"}], [STORY, b], [])[0]["id"] == "b-1"
    assert pick_story(ITEMS, [{"story_id": "a-1"}, {"story_id": "b-1"}], [STORY, b], []) is None
    assert unused([], [STORY], [{"story_id": "a-1"}, {"story_id": "a-1"}]) == []


def test_chart_shows_only_numbers_the_post_states():
    post = "Keywords alone got 63% right. The final design got 92.5% on 40 held-out questions."
    assert [r["value"] for r in story_results_in_post(STORY, post)] == ["63%", "92.5%"]
    path, alt = render_story_chart(STORY, ITEMS[0], post)
    assert Image.open(path).size == (1080, 1350)
    assert "63%" in alt and "92.5%" in alt and "83%" not in alt
    assert render_story_chart(STORY, ITEMS[0], "Only 63% here.") is None


@pytest.mark.asyncio
async def test_refill_reads_project_documents_and_keeps_only_verified_stories(tmp_path):
    path = str(tmp_path / "stories.json")
    reply = json.dumps({"stories": [{k: STORY[k] for k in ("question", "test", "results", "decision", "chart_title")},
                                    {**{k: STORY[k] for k in ("question", "test", "decision", "chart_title")},
                                     "results": [{"label": "Invented", "value": "71%"}, {"label": "Also", "value": "12 ms"},
                                                 {"label": "Third", "value": "63%"}]}]})
    with patch("app.services.story_bank.fetch_docs", AsyncMock(return_value=(DOCS * 5, ["https://github.com/o/a/blob/HEAD/README.md"]))), \
         patch("app.services.llm_service.call_llm_with_fallback", AsyncMock(return_value=reply)):
        status = await refill(ITEMS, [], settings=None, path=path)
    stories = load_stories(path)
    assert [s["subject"] for s in stories] == ["Project A", "Project B"]  # one verified story from each project's documents
    assert stories[0]["sources"] == ["https://github.com/o/a/blob/HEAD/README.md"]
    assert "2 new" in status


def test_feedback_is_kept(tmp_path):
    path = str(tmp_path / "feedback.json")
    add_feedback({"story_id": "a-1", "comment": "too many numbers"}, path)
    assert json.load(open(path, encoding="utf-8"))[0]["comment"] == "too many numbers"
