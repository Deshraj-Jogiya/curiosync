"""The alt text LinkedIn reads: the post's claim first, then the chart, then the demanded skills the story shows."""

from unittest.mock import patch

from app.services.alt_text import describe


def test_alt_text_leads_with_the_posts_claim_and_names_skills():
    market = {"skills": [{"term": "Python", "share": 50, "evidence": "work"}, {"term": "SQL", "share": 40, "evidence": "work"}]}
    with patch("app.services.market_skills.load", return_value=market):
        out = describe("Bar chart: alerts 1,110", "My SQL check caught 40 of 4,069 #Python\n\nBody", {"question": "Python and SQL"})
    assert out == "My SQL check caught 40 of 4,069. Bar chart: alerts 1,110. Skills shown: Python, SQL."


def test_alt_text_without_a_story_keeps_the_chart_and_does_not_repeat_the_claim():
    assert describe("My claim here, then the chart", "My claim here, then the chart\n\nx") == "My claim here, then the chart."
