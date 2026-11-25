"""Chart data cached in the story bank, read from the projects' own CSV shapes, and the low-runway alarm."""

from datetime import date
from unittest.mock import AsyncMock, patch

import pytest

from app.services import runway_alarm
from app.services.post_charts import render_curves
from app.services.story_bank import cache_media, groups_from_csv, media_runway, series_from_csv

PREP = "week_start,files,manual_hours,pipeline_seconds\n" + "\n".join(
    f"2025-04-{d:02d},35,{4 + d / 3:.2f},1.1" for d in (1, 8, 15, 22, 29))
LAYERS = "layer,flagged,precision,recall\nmodel,19,0.9474,0.383\nrule,45,1.0,0.9574\ncombined,46,0.9783,0.9574\n"
ITEM = {"title": "Land Use", "github_url": "https://github.com/x/land-use", "notes": "why"}


def test_series_from_csv_reads_the_column_the_story_names():
    story = {"question": "How many manual hours did weekly prep take?", "results": []}
    c = series_from_csv(PREP, "exports/prep_hours.csv", story)
    assert c["x_label"] == "days from 2025-04-01"
    assert list(c["groups"]) == ["manual hours"]
    assert [p[0] for p in c["groups"]["manual hours"]] == [0, 7, 14, 21, 28]


def test_series_from_csv_guesses_nothing_when_no_column_is_the_storys():
    assert series_from_csv(PREP, "p.csv", {"question": "Was the map right?"}) is None
    assert series_from_csv(PREP, "p.csv", {"question": "x"}, column="manual_hours") is not None


def test_groups_from_csv_reads_a_comparison_table():
    g = groups_from_csv(LAYERS, "exports/detection_layers.csv")
    assert g["group"] == "layer"
    assert [r["name"] for r in g["rows"]] == ["model", "rule", "combined"]
    assert g["rows"][0]["values"]["recall"] == "0.383"


def test_one_series_is_drawn_as_curves():
    story = {"question": "How many manual hours did weekly prep take?", "chart_title": "Manual prep hours each week",
             "decision": "", "results": []}
    story["curves"] = series_from_csv(PREP, "exports/prep_hours.csv", story)
    assert render_curves(story, {"title": "Land Use"}) is not None


@pytest.mark.asyncio
async def test_cache_media_stores_chart_data_and_stamps_the_check():
    stories = [{"id": "a", "subject": "Land Use"}, {"id": "b", "subject": "Land Use", "media_checked": str(date.today())}]
    groups = {"group": "layer", "columns": ["recall"], "rows": []}
    with patch("app.services.story_bank.with_excerpt", AsyncMock(side_effect=lambda s, i: {**s, "groups": groups})):
        n = await cache_media(stories, [ITEM])
    assert n == 1
    assert stories[0]["groups"] == groups and stories[0]["media_checked"] == str(date.today())
    assert "groups" not in stories[1]


def test_media_runway_counts_only_drawable_stories_with_notes():
    stories = [{"id": "a", "subject": "Land Use", "question": "q1"}, {"id": "b", "subject": "Land Use", "question": "q2"},
               {"id": "c", "subject": "No Notes", "question": "q3"}]
    items = [ITEM, {"title": "No Notes"}]
    assert media_runway(items, [], stories, lambda st, it: st["id"] != "b") == 1


@pytest.mark.asyncio
async def test_alarm_without_a_token_only_reports(monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
    out = await runway_alarm.check(2, repo="", token="")
    assert out.startswith("2 drawable stories left")


def test_a_flat_single_series_is_not_media():
    flat = "week_start,manual_hours" + chr(10) + chr(10).join(f"2025-04-{d:02d},{10 + d / 100:.2f}" for d in (1, 8, 15, 22, 29))
    assert series_from_csv(flat, "p.csv", {"question": "How many manual hours?"}) is None


def test_media_runway_applies_the_pickers_demand_gate_and_rejections():
    market = {"skills": [{"term": "Python", "share": 50, "evidence": "work"}, {"term": "SQL", "share": 40, "evidence": "work"}]}
    stories = [{"id": "a", "subject": "Land Use", "question": "Python and SQL check"},
               {"id": "b", "subject": "Land Use", "question": "Python only"},
               {"id": "c", "subject": "Land Use", "question": "Python and SQL again, other data"}]
    rejected = [{"story_id": "c", "verdict": "reject", "date": "2026-11-01"}] * 2
    with patch("app.services.market_skills.load", return_value=market), \
            patch("app.services.story_bank.load_feedback", return_value=rejected):
        assert media_runway([ITEM], [], stories, lambda st, it: True) == 1


def test_a_document_page_that_only_repeats_earlier_numbers_is_left_out(tmp_path):
    from app.services import post_document as pd

    def page(alt):
        f = tmp_path / f"{abs(hash(alt))}.png"
        f.write_bytes(b"x")
        return lambda *a, **k: (str(f), alt)

    story = {"results": [{"label": "a", "value": "1"}] * 4, "chart_title": "T"}
    with patch.object(pd, "render_curves", lambda *a: None), \
            patch.object(pd, "render_group_chart", page("Bar chart, "+"Alerts 1,110 and 4,942; caught 1,464")), \
            patch.object(pd, "render_story_chart", page("Bar chart, "+"Alerts 1,110 and 4,942 again")), \
            patch.object(pd, "render_series", lambda *a: None), \
            patch.object(pd, "render_stage_flow", lambda *a: None), \
            patch.object(pd, "comparison_grid", lambda r: None), \
            patch.object(pd, "visual_fill", lambda p: 1.0), patch.object(pd, "overflows", lambda p: False):
        assert pd.render_story_document(story, {"title": "X"}, "") is None
    with patch.object(pd, "render_curves", lambda *a: None), \
            patch.object(pd, "render_group_chart", page("Bar chart, "+"Alerts 1,110 and 4,942; caught 1,464")), \
            patch.object(pd, "render_story_chart", page("Bar chart, "+"Precision 0.2962, recall 0.565, alerts 4,069")), \
            patch.object(pd, "render_series", lambda *a: None), \
            patch.object(pd, "render_stage_flow", lambda *a: None), \
            patch.object(pd, "comparison_grid", lambda r: None), \
            patch.object(pd, "visual_fill", lambda p: 1.0), patch.object(pd, "overflows", lambda p: False), \
            patch("PIL.Image.open") as op:
        op.return_value.convert.return_value.save = lambda *a, **k: None
        doc = pd.render_story_document(story, {"title": "X"}, "")
    assert doc and len(doc[1]) == 2


def test_a_story_with_one_chart_continues_with_the_projects_other_findings(tmp_path):
    from app.services import post_document as pd

    def page(alt):
        f = tmp_path / f"{abs(hash(alt))}.png"
        f.write_bytes(b"x")
        return (str(f), alt)

    story = {"id": "a", "results": [{"label": "a", "value": "1"}], "chart_title": "T", "simulated": True}
    sib_real = {"id": "b", "chart_title": "S", "simulated": False}
    seen = []

    def group(st, item):
        seen.append((st["id"], item.get("simulated")))
        return page("Bar chart, "+"Monday 156; Tuesday 0; Saturday 156") if st["id"] == "a" else page("Bar chart, "+"Software 6; Retail 6; Finance 5")

    with patch.object(pd, "render_curves", lambda *a: None), \
            patch.object(pd, "render_group_chart", group), \
            patch.object(pd, "render_story_chart", lambda *a: None), \
            patch.object(pd, "render_series", lambda *a: None), \
            patch.object(pd, "render_stage_flow", lambda *a: None), \
            patch.object(pd, "comparison_grid", lambda r: None), \
            patch.object(pd, "visual_fill", lambda p: 1.0), patch.object(pd, "overflows", lambda p: False), \
            patch("PIL.Image.open") as op:
        op.return_value.convert.return_value.save = lambda *a, **k: None
        assert pd.render_story_document(story, {"title": "X"}, "") is None  # one chart alone is no carousel
        doc = pd.render_story_document(story, {"title": "X"}, "", [sib_real])
    assert doc and len(doc[1]) == 2
    assert [s for i, s in seen if i == "b"] and not any(s for i, s in seen if i == "b")  # the borrowed page is labelled by its own data, not the main story's "simulated"


def test_document_pages_that_are_number_cards_repeats_or_overflow_are_refused(tmp_path):
    from PIL import Image
    from app.services import post_document as pd
    from app.services.post_visual import BG, H, W

    clean = tmp_path / "clean.png"
    Image.new("RGB", (W, H), BG).save(clean)
    spill = tmp_path / "spill.png"
    im = Image.new("RGB", (W, H), BG)
    im.paste((200, 200, 200), (W - 20, 300, W, 340))
    im.save(spill)
    with patch.object(pd, "visual_fill", lambda p: 1.0):
        assert pd.page_problem((str(clean), "Results: 60 to 21"), set(), []) == "not a chart (a card of numbers)"
        assert pd.page_problem((str(clean), "Before and after: 60 to 21"), set(), []) == "not a chart (a card of numbers)"
        assert pd.page_problem((str(spill), "Bar chart, x: 1 2 3"), set(), []) == "text runs past the card"
        assert pd.page_problem((str(clean), "Line chart, loss: 1.779 1.760 1.65"), {"1.779", "1.760", "1.65"}, []) \
            == "mostly numbers an earlier page already shows"
        assert pd.page_problem((str(clean), "Bar chart, x: 1 2 3"), set(), []) is None


def test_a_finding_used_by_an_upcoming_post_is_reserved(tmp_path):
    import json
    from app.services.approved_queue import reserved_story_ids

    q = tmp_path / "q.json"
    q.write_text(json.dumps([
        {"id": "p1", "text": "one", "history_entry": {"story_id": "a"}, "document_story_ids": ["b"]},
        {"id": "p2", "text": "two", "history_entry": {"story_id": "c"}},
    ]))
    assert reserved_story_ids([{"approved_id": "p2"}], str(q)) >= {"a", "b"}


def test_a_line_needs_an_ordered_x_axis_and_a_bar_page_needs_three_bars(tmp_path):
    from PIL import Image
    from app.services import post_document as pd
    from app.services.post_charts import is_sequence_axis
    from app.services.post_visual import BG, H, W

    assert is_sequence_axis("day") and is_sequence_axis("Epoch") and is_sequence_axis("trading_day")
    assert not is_sequence_axis("skill_vs_last_year")
    clean = tmp_path / "c.png"
    Image.new("RGB", (W, H), BG).save(clean)
    with patch.object(pd, "visual_fill", lambda p: 1.0):
        assert pd.page_problem((str(clean), "Bar chart, fairness: ratio 0.963; alerts 0"), set(), []) == "too few bars to compare"


def test_the_queue_audit_flags_missing_media_repeats_and_clashing_days(tmp_path, monkeypatch):
    import json
    from PIL import Image
    from app import queue_audit
    from app.services.post_visual import BG, H, W

    monkeypatch.chdir(tmp_path)
    Image.new("RGB", (W, H), BG).save("ok.png")
    q = tmp_path / "q.json"
    q.write_text(json.dumps([
        {"id": "a", "text": "one", "image": "ok.png", "post_day": "2026-12-01", "history_entry": {"story_id": "s1"},
         "document_story_ids": ["x"]},
        {"id": "b", "text": "two", "image": "gone.png", "post_day": "2026-12-01", "history_entry": {"story_id": "s2"},
         "document": "gone.pdf", "document_story_ids": ["x"]},
    ]))
    found = queue_audit.problems([{"story_id": "s2", "text": "old"}], str(q))
    assert any("image missing" in p for p in found)
    assert any("document missing" in p for p in found)
    assert any("same post day" in p for p in found)
    assert any("already posted" in p for p in found)
    assert any("borrows x" in p for p in found)
    assert not any(p.startswith("2026-12-01 a:") for p in found)


def test_scientific_notation_is_one_number():
    from app.services.post_charts import number
    from app.services.post_visual import _value_number

    assert _value_number("5.4e-70") == 5.4e-70 and number("5.4e-70") == 5.4e-70
    assert _value_number("1,200") == 1200.0


def test_a_story_shown_as_a_page_of_a_queued_document_is_not_picked_again():
    from app.services import story_bank

    stories = [{"id": "t-1", "subject": "Tax", "question": "q1"}, {"id": "t-2", "subject": "Tax", "question": "q2"}]
    with patch("app.services.approved_queue.load_queue", return_value=[{"id": "p", "document_story_ids": ["t-2"]}]):
        assert [s["id"] for s in story_bank.unused([], stories, [])] == ["t-1"]
