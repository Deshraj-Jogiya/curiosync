"""Drafts that passed every rule but read below the approved posts (Clinical Trials draft for Mon 2026-11-16)."""

from app.services.post_document import story_image
from app.services.post_rules import flow_problems, unsupported_numbers
from app.services.story_bank import enrich, story_text
from app.services.summarizer_service import is_hard

EXCERPT = """## Does a higher dosage change survival?

| Arm | Survival at day 365 | Median survival, Kaplan-Meier (days) | Mortality |
|---|---|---|---|
| Control | 0.1582 | 144 | 69.47% |
| Low-dosage | 0.3327 | 288 | 60.0% |
| High-dosage | 0.5320 | not reached | 42.5% |
"""

STORY = {"id": "clinical-1", "subject": "Clinical Trials Patient Outcomes Analysis", "question": "Does a higher dosage change survival?",
         "test": "Kaplan-Meier curves across three arms", "decision": "Survival differs between every pair of arms, and the high-dosage arm "
         "survives longest.", "chart_title": "Survival by dosage arm", "detail": "All 250 patient records are simulated.",
         "results": [{"label": "Survival at day 365", "value": "0.1582"}, {"label": "Median survival (days)", "value": "118.0"},
                     {"label": "Mortality", "value": "69.47%"}], "excerpt": EXCERPT, "simulated": False}

DRAFT = """Testing clinical trial cohorts showed that patient survival differs by dosage, with the high-dosage arm surviving longest.

Clinical Trials Patient Outcomes Analysis is a personal portfolio project. I built it to learn how illnesses work.

Before drawing conclusions about treatment efficacy, an engineer must verify whether a higher dosage changes outcomes.

So I fitted Kaplan-Meier curves across three treatment arms over that full year.

That finding made the outcome clear. Patient survival differs between every pair of arms, and the high-dosage arm survives longest.

When evaluating clinical trial outcomes across several arms, do you rely on log-rank tests or on Cox models?

#DataEngineering #MachineLearning"""


def test_every_group_row_of_the_write_up_reaches_the_writer():
    s = enrich(STORY)
    assert [r["name"] for r in s["groups"]["rows"]] == ["Control", "Low-dosage", "High-dosage"]
    assert "High-dosage: Survival at day 365 0.5320" in story_text(s)


def test_a_value_the_write_up_no_longer_states_is_dropped():
    assert "118.0" not in [r["value"] for r in enrich(STORY)["results"]]


def test_simulated_data_named_in_the_write_up_is_marked_and_its_omission_is_a_truth_problem():
    assert enrich(STORY)["simulated"] is True
    assert is_hard("the project used simulated or synthetic data; the post must say so")


def test_a_share_may_be_written_as_a_percent_with_its_stated_precision():
    assert unsupported_numbers("53.20% and 53.2%", "0.5320") == []
    assert unsupported_numbers("53.21%", "0.5320") == ["53.21%"]


def test_a_close_that_repeats_the_first_line_and_a_general_stake_are_flagged():
    found = flow_problems(DRAFT)
    assert any(p.startswith("closing: the result paragraph repeats the first line") for p in found)
    assert any(p.startswith('voice: "an engineer must"') for p in found)


def test_the_image_compares_the_groups_instead_of_repeating_the_post():
    s = enrich(STORY)
    path, alt, kind = story_image(s, {"title": s["subject"], "context": "Personal portfolio project"}, DRAFT)
    assert kind == "group comparison"
    assert "High-dosage 0.5320" in alt and "not reached" not in alt and "Simulated data" in alt


CSV = "group_name,day,survival_probability,at_risk\n" + "".join(
    f"{g},{d},{p},{n}\n" for g, pts in {"Control": [(0, 1.0), (100, 0.6), (365, 0.1582)],
                                        "Low-dosage": [(0, 1.0), (100, 0.8), (365, 0.3327)],
                                        "High-dosage": [(0, 1.0), (100, 0.9), (365, 0.532)]}.items() for d, p in pts for n in [90])


def test_curves_come_from_the_projects_own_exported_data():
    from app.services.story_bank import curves_from_csv

    c = curves_from_csv(CSV, "exports/km_curves.csv")
    assert (c["x_label"], c["y_label"]) == ("day", "survival_probability")
    assert c["groups"]["High-dosage"][-1] == [365.0, 0.532]
    assert curves_from_csv("a,b\n1,2\n3,4\n", "x.csv") is None  # no group column: nothing is guessed


def test_the_curves_image_is_preferred_and_its_alt_text_names_the_source_file():
    from app.services.story_bank import curves_from_csv

    s = {**enrich(STORY), "curves": curves_from_csv(CSV, "exports/km_curves.csv")}
    path, alt, kind = story_image(s, {"title": s["subject"], "context": "Personal portfolio project"}, DRAFT)
    assert kind == "curves" and "exports/km_curves.csv" in alt and "High-dosage 53.2%" in alt
