"""Tests for reading post facts from the portfolio profile, and for the link and self-reference checks."""

from app.services.compliance_service import check_compliance, humanize_draft
from app.services.profile_source import featurable_items, plain, profile_context
from tests.sample_profile import SAMPLE_PROFILE


def test_plain_strips_html_and_entities():
    assert plain("Raised <strong>25%</strong> with A &amp; B") == "Raised 25% with A & B"


def test_projects_exclude_team_work_and_curiosync():
    names = [p["title"] for p in featurable_items(SAMPLE_PROFILE, "project")]
    assert names == ["Job Search CRM & AI Application Tailoring Center", "Job Search dbt Warehouse"]


def test_experience_facts_are_plain_text():
    exp = featurable_items(SAMPLE_PROFILE, "experience")[0]
    assert exp["org"] == "Objectways Technologies LLC"
    assert exp["facts"] == ["Lifted dataset accuracy by 20% across 10,000+ samples."]


def test_context_uses_profile_title():
    assert profile_context(SAMPLE_PROFILE).startswith("Title: Data Engineer & Machine Learning Engineer")


def test_link_lines_are_removed_and_tech_names_kept():
    text = "Built on ASP.NET and Node.js.\n\nVisit deshraj-jogiya.github.io to play.\n\nRepo: https://github.com/x/y\n\nDone."
    out = humanize_draft(text)
    assert "github" not in out
    assert "ASP.NET and Node.js" in out
    assert check_compliance(out, [])["blocking"] == []


def test_self_reference_blocks():
    assert check_compliance("This post was fully compiled and published by CurioSync.", [])["blocking"]
