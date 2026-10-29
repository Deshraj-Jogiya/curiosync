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


def test_stat_card_numbers_are_results_used_once():
    from app.services.post_visual import _numeric_facts

    item = {"facts": [
        "Recognises 29 word signs from video, 75.9% top-1 on held-out clips.",
        "Teaches 7 concepts and recognises 29 word signs, 75.9% top-1.",  # same figure restated
        "Applied Pareto analysis: the top 20% of customers generate 79.9% of revenue (80/20).",
        "Found a real 404 on a guessed tile URL and fixed it.",  # an error code, not a result
        "All 11 tests hit the live APIs.",
    ]}
    numbers = [n for n, _ in _numeric_facts(item)]
    assert numbers == ["75.9%", "20%", "11"]


def test_stat_card_never_draws_a_number_without_its_sentence(monkeypatch):
    from app.services import post_visual

    long_text = "word " * 400
    item = {"title": "Sample", "facts": [f"Reached 42% on {long_text}", "Cut latency by 30% on the main path."]}
    seen = []
    real = post_visual.fit_text
    monkeypatch.setattr(post_visual, "fit_text", lambda d, t, *a, **k: seen.append(t) or real(d, t, *a, **k))
    path, alt = post_visual.render_stat_card(item)
    assert "30%" in alt and "42%" not in alt


def test_stage_times_that_add_up_to_a_total_draw_as_one_split_bar():
    from app.services.post_visual import _short_labels, parts_of_total
    results = [{"label": "Median decode frames time", "value": "76.2 ms"}, {"label": "Median hand features time", "value": "997.0 ms"},
               {"label": "Median model inference time", "value": "8.9 ms"},
               {"label": "Median total processing time per request", "value": "1081.2 ms"},
               {"label": "Median whole request time", "value": "1090.5 ms"}]
    parts, total, others = parts_of_total(results)
    assert [p["value"] for p in parts] == ["997.0 ms", "76.2 ms", "8.9 ms"] and total["value"] == "1081.2 ms" and len(others) == 1
    names, stat = _short_labels(parts + [total] + others)
    assert stat == "Median" and names[0] == "Hand features" and names[-1] == "Whole request"
    assert parts_of_total([{"label": "Recall", "value": "0.91"}, {"label": "Precision", "value": "0.88"}]) is None
