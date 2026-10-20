"""Tests for the post image: fact-checked card, fitting text instead of cutting it, and no generic fallback."""

import os
from unittest.mock import patch

import pytest
from PIL import Image

from app.services import post_visual

ITEM = {"title": "Job Market Lakehouse", "kind": "project", "context": "Personal portfolio project", "simulated": True,
        "facts": ["A PySpark and Scala Spark SQL pipeline over 60k synthetic postings.", "Wrote 11 Great Expectations checks.",
                  "Built an Airflow DAG verified end to end."]}
FACTS = " ".join(ITEM["facts"])
META = ('{"headline_number": "11", "headline_label": "Great Expectations checks", "steps": ['
        '{"label": "Generate postings", "detail": "60k synthetic postings"}, {"label": "Transform", "detail": "PySpark and Scala Spark SQL"},'
        '{"label": "Validate", "detail": "Great Expectations checks"}, {"label": "Orchestrate", "detail": "Airflow DAG verified end to end"}],'
        '"alt_text": "Card"}')


def _size(path):
    with Image.open(path) as im:
        return im.size


@pytest.mark.asyncio
async def test_breakdown_card_is_portrait_and_grounded(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    async def llm(*a, **k):
        return META
    with patch("app.services.llm_service.call_llm_with_fallback", llm):
        path, alt, kind = await post_visual.build_visual(ITEM, object(), FACTS)
    assert kind == "breakdown" and _size(path) == (1080, 1350) and alt == "Card"
    os.remove(path)


@pytest.mark.asyncio
async def test_card_with_an_invented_tool_falls_back_to_the_stat_card(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    async def llm(*a, **k):
        return META.replace("Airflow DAG", "Kafka stream")
    with patch("app.services.llm_service.call_llm_with_fallback", llm):
        path, alt, kind = await post_visual.build_visual(ITEM, object(), FACTS)
    assert kind == "stat" and "Kafka" not in alt
    os.remove(path)


def test_text_that_cannot_fit_is_refused_not_cut():
    img, draw = post_visual._canvas()
    assert post_visual.fit_text(draw, "word " * 400, 300, 2, [30, 24]) is None
    font, lines = post_visual.fit_text(draw, "short label", 900, 1, [30])
    assert lines == ["short label"]


def test_real_visual_is_copied_not_handed_out(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs("assets/visuals")
    Image.new("RGB", (1200, 800), "white").save("assets/visuals/lake.png")
    (tmp_path / "assets/visuals/index.json").write_text('{"Job Market Lakehouse": {"file": "lake.png", "alt": "DAG run"}}')
    path, alt = post_visual._real_visual(ITEM)
    assert alt == "DAG run" and os.path.abspath(path) != os.path.abspath("assets/visuals/lake.png")
    os.remove(path)
    assert os.path.exists("assets/visuals/lake.png")
