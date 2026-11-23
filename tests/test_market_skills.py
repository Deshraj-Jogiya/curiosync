"""Posts showcase the skills employers require in the roles the owner applies to (owner, 2026-11-18)."""
import json

import pytest

from app.services import market_skills
from app.services.post_rules import skill_problems
from app.services.story_bank import pick_story

MARKET = {"generated_at": "2026-11-19", "target_postings": 1113, "skills": [
    {"term": "Python", "share": 53, "evidence": "work"}, {"term": "SQL", "share": 36, "evidence": "work"},
    {"term": "Statistics", "share": 24, "evidence": "work"}, {"term": "R", "share": 10, "evidence": "none"},
    {"term": "RAG", "share": 9, "evidence": "work"}]}

ITEMS = [{"kind": "project", "title": "Project A", "facts": ["x"]}, {"kind": "project", "title": "Project B", "facts": ["y"]}]


@pytest.fixture(autouse=True)
def market(tmp_path, monkeypatch):
    path = tmp_path / "market_skills.json"
    path.write_text(json.dumps(MARKET), encoding="utf-8")
    monkeypatch.setattr(market_skills, "PATH", str(path))


def story(id_, subject, question, skills):
    return {"id": id_, "subject": subject, "question": question, "test": "", "results": [], "decision": "", "skills": skills}


def test_only_skills_his_work_shows_count_and_short_names_match_whole_words():
    assert [s["term"] for s in market_skills.demanded()] == ["Python", "SQL", "Statistics", "RAG"]
    assert market_skills.skills_in("A RAG answer from a SQL query") and \
        [s["term"] for s in market_skills.skills_in("RAGE against SQLx")] == []
    assert [s["term"] for s in market_skills.skills_in("a KS test on the statistical gap")] == ["Statistics"]


def test_a_story_that_shows_no_demanded_skill_is_never_picked():
    font = story("a-1", "Project A", "What does the min_body_font_pt correction change?", ["resume_rules.yaml"])
    assert pick_story(ITEMS, [], [font], []) is None


def test_the_more_demanded_story_comes_first_even_when_its_project_posted_more_recently():
    low = story("a-1", "Project A", "Does the RAG answer hold up statistically?", ["Statistics"])
    high = story("b-1", "Project B", "Is the Python job faster than the SQL view?", ["Python", "SQL"])
    assert pick_story(ITEMS, [{"subject": "Project B"}], [low, high], [])[0]["id"] == "b-1"


def test_a_draft_must_name_the_skills_early_and_tag_one():
    item = {"showcase_skills": ["Python", "SQL"]}
    good = "I rebuilt the check in Python and moved the join into SQL.\n\nIt now runs in 2 s.\n\n#Python #SQL"
    assert skill_problems(good, item) == []
    late = ("A long opening that names nothing an employer screens for, and keeps going for a while so the reader is still "
            "waiting for the point well past the line where LinkedIn cuts the preview off and shows see more.\n\n"
            "Then Python and SQL appear.\n\n#Python")
    assert any("first 210 characters" in p for p in skill_problems(late, item))
    vague = "I rebuilt the check and moved the join.\n\n#DataEngineering"
    problems = skill_problems(vague, item)
    assert any("names 0 of the skills" in p for p in problems) and any("hashtags" in p for p in problems)


def test_a_story_showing_only_one_demanded_skill_is_not_enough():
    only_python = story("a-1", "Project A", "Which users post most?", ["Python"])
    assert pick_story(ITEMS, [], [only_python], []) is None


def test_tools_count_as_the_skill_they_are():
    terms = lambda text: [s["term"] for s in market_skills.skills_in(text)]  # noqa: E731
    assert "Python" in terms("cleaned with pandas and GeoPandas")
    assert "SQL" in terms("queried in DuckDB")
    assert "Statistics" in terms("a chi-square test")
