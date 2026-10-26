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
         patch("app.services.llm_service.call_llm_with_fallback", AsyncMock(return_value=reply)),          patch("app.services.story_bank.head_sha", AsyncMock(return_value="sha1")):
        status = await refill(ITEMS, [], settings=None, path=path, meta_path=str(tmp_path / "meta.json"))
    stories = load_stories(path)
    assert [s["subject"] for s in stories] == ["Project A", "Project B"]  # one verified story from each project's documents
    assert stories[0]["sources"] == ["https://github.com/o/a/blob/HEAD/README.md"]
    assert "2 new" in status


def test_feedback_is_kept(tmp_path):
    path = str(tmp_path / "feedback.json")
    add_feedback({"story_id": "a-1", "comment": "too many numbers"}, path)
    assert json.load(open(path, encoding="utf-8"))[0]["comment"] == "too many numbers"


def test_skills_not_featured_lately_come_first_within_a_project():
    old = {**STORY, "id": "a-1", "skills": ["Python", "SQL"]}
    fresh = {**STORY, "id": "a-2", "skills": ["Isolation Forest", "Dagster"],
             "results": [{"label": "x", "value": "45"}, {"label": "y", "value": "18"}, {"label": "z", "value": "43"}]}
    history = [{"story_id": "z-9", "subject": "Project B"}]
    stories = [old, fresh, {**STORY, "id": "z-9", "subject": "Project B", "skills": ["Python", "SQL"]}]
    assert pick_story(ITEMS, history, stories, [])[0]["id"] == "a-2"


def test_when_every_story_is_used_the_oldest_comes_back_after_six_months_as_a_repeat():
    from datetime import date

    history = [{"story_id": "a-1", "subject": "Project A", "date": "2026-01-05"}]
    assert pick_story(ITEMS, history, [STORY], [], today=date(2026, 5, 1)) is None
    story, _ = pick_story(ITEMS, history, [STORY], [], today=date(2026, 8, 1))
    assert story["id"] == "a-1" and story["repeat_of"] == "2026-01-05"


@pytest.mark.asyncio
async def test_a_project_is_read_again_when_its_repository_changes_and_repeated_tests_are_skipped(tmp_path):
    path, meta = str(tmp_path / "stories.json"), str(tmp_path / "meta.json")
    reply = json.dumps({"stories": [{k: STORY[k] for k in ("question", "test", "results", "decision", "chart_title")}]})
    llm = AsyncMock(return_value=reply)
    sha = AsyncMock(return_value="sha1")
    with patch("app.services.story_bank.fetch_docs", AsyncMock(return_value=(DOCS * 5, ["src"]))), \
         patch("app.services.llm_service.call_llm_with_fallback", llm), patch("app.services.story_bank.head_sha", sha):
        await refill(ITEMS[:1], [], settings=None, path=path, meta_path=meta)
        assert llm.await_count == 1
        await refill(ITEMS[:1], [], settings=None, path=path, meta_path=meta)  # same commit: not read again
        assert llm.await_count == 1
        sha.return_value = "sha2"
        status = await refill(ITEMS[:1], [], settings=None, path=path, meta_path=meta)  # new commit: read again
        assert llm.await_count == 2 and "0 new" in status  # the same test is not added twice
    assert len(load_stories(path)) == 1


def test_series_are_checked_against_the_documents():
    from app.services.story_bank import verify_series

    docs = "Accuracy on day 1 was 0.9988, on day 40 0.91 and on day 60 0.83. Latency went from 7.5 s to 0.9 s."
    line = {"type": "line", "points": [{"x": "1", "y": "0.9988"}, {"x": "40", "y": "0.91"}, {"x": "60", "y": "0.83"}]}
    assert verify_series(line, docs) == []
    assert verify_series({**line, "points": line["points"][:2]}, docs)  # too short for a line
    invented = {"type": "line", "points": [{"x": "1", "y": "0.9988"}, {"x": "40", "y": "0.95"}, {"x": "60", "y": "0.83"}]}
    assert "not in the documents" in verify_series(invented, docs)[0]
    assert verify_series({"type": "before_after", "points": [{"label": "Latency", "before": "7.5 s", "after": "0.9 s"}]}, docs) == []
    assert verify_series({"type": "pie", "points": []}, docs)


def test_the_image_follows_the_shape_of_the_data():
    from app.services.post_document import story_image

    item = ITEMS[0]
    with_series = {**STORY, "series": {"type": "scatter", "title": "Accuracy against size", "x_label": "MB", "y_label": "%",
                                       "points": [{"label": "A", "x": "0", "y": "63"}, {"label": "B", "x": "46", "y": "83"},
                                                  {"label": "C", "x": "57", "y": "92.5"}]}}
    assert story_image(with_series, item, "")[2] == "scatter"
    grid = {**STORY, "results": [{"label": "Rule precision", "value": "1.0"}, {"label": "Model precision", "value": "0.9474"},
                                 {"label": "Rule recall", "value": "0.9574"}, {"label": "Model recall", "value": "0.383"}]}
    assert story_image(grid, item, "")[2] == "table"
    assert story_image(STORY, item, "Keywords 63% and final 92.5%.")[2] == "results chart"


@pytest.mark.asyncio
async def test_reading_a_repo_again_adds_chart_data_to_a_story_already_in_the_bank(tmp_path):
    path, meta = str(tmp_path / "stories.json"), str(tmp_path / "meta.json")
    plain = json.dumps({"stories": [{k: STORY[k] for k in ("question", "test", "results", "decision", "chart_title")}]})
    series = {"type": "before_after", "title": "t", "points": [{"label": "Final", "before": "63%", "after": "92.5%"}]}
    richer = json.dumps({"stories": [{**{k: STORY[k] for k in ("question", "test", "results", "decision", "chart_title")},
                                      "series": series, "skills": ["reranker"]}]})
    sha = AsyncMock(return_value="sha1")
    llm = AsyncMock(return_value=plain)
    with patch("app.services.story_bank.fetch_docs", AsyncMock(return_value=(DOCS * 5, ["src"]))), \
         patch("app.services.llm_service.call_llm_with_fallback", llm), patch("app.services.story_bank.head_sha", sha):
        await refill(ITEMS[:1], [], settings=None, path=path, meta_path=meta)
        llm.return_value, sha.return_value = richer, "sha2"
        await refill(ITEMS[:1], [], settings=None, path=path, meta_path=meta)
    stories = load_stories(path)
    assert len(stories) == 1 and stories[0]["id"] == "project-a-1"
    assert stories[0]["series"]["type"] == "before_after" and stories[0]["skills"] == ["reranker"]


def test_story_json_is_read_through_fences_and_surrounding_text():
    from app.services.story_bank import parse_stories

    assert parse_stories('Here you go:\n```json\n{"stories": [{"question": "q"}]}\n```') == [{"question": "q"}]
    assert parse_stories("no json at all") is None
    assert parse_stories('{"stories": [') is None


def test_documents_are_read_in_pieces_that_fit_the_free_tier():
    from app.services.story_bank import doc_chunks

    docs = "# FILE: docs/FINDINGS.md\n" + ("Finding paragraph.\n\n" * 900) + "# FILE: README.md\nShort readme."
    chunks = doc_chunks(docs, size=14000)
    assert all(len(c) <= 14000 for c in chunks) and len(chunks) >= 2
    assert chunks[0].startswith("# FILE: docs/FINDINGS.md") and "Short readme." in chunks[-1]
