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
