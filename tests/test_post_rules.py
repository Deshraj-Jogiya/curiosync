"""Tests for the mechanical post rules: these are the safety net now that posts are not reviewed one by one."""

from app.services.post_rules import (body_similarity, check_draft, tidy_hashtags, unsupported_numbers, unsupported_tools)

FACTS = ("Job Market Lakehouse: a PySpark and Scala Spark SQL pipeline over 60k synthetic postings. Wrote 11 Great Expectations checks. "
         "Built an Airflow DAG. Cut processing time by 30%.")
SOLO_SIM = {"kind": "project", "solo": True, "simulated": True}


def _post(body: str, first: str = "I wrote 11 Great Expectations checks before trusting a synthetic dataset.") -> str:
    filler = " The pipeline runs PySpark over simulated postings and each stage is checked." * 14
    return f"{first}\n\n{body}{filler}\n\nSo every stage is checked before anything reads it.\n\n#DataEngineering #PySpark"


def test_clean_post_passes():
    assert check_draft(_post("I built it on simulated data."), SOLO_SIM, FACTS, []) == []


def test_invented_number_is_caught():
    assert unsupported_numbers("Cut processing time by 45% across 60k postings", FACTS) == ["45%"]
    assert unsupported_numbers("Three checks, step 2, 60k postings, 30%", FACTS) == []


def test_tool_not_in_facts_is_caught():
    assert unsupported_tools("Streamed it through Kafka into Snowflake", FACTS) == ["snowflake", "kafka"] or \
        sorted(unsupported_tools("Streamed it through Kafka into Snowflake", FACTS)) == ["kafka", "snowflake"]
    assert unsupported_tools("Spark jobs and PySpark", FACTS) == []


def test_we_on_solo_project_is_caught():
    problems = check_draft(_post("We built it on simulated data."), SOLO_SIM, FACTS, [])
    assert any("we/our/us" in p for p in problems)


def test_simulation_must_be_disclosed():
    problems = check_draft(_post("I built it.", first="I wrote 11 Great Expectations checks before trusting the data.")
                           .replace("simulated", "real"), SOLO_SIM, FACTS, [])
    assert any("simulated or synthetic" in p for p in problems)


def test_filler_bait_and_backstory_are_caught():
    problems = check_draft(_post("This was a crucial step. Our old process was a bottleneck. Like if you agree."), SOLO_SIM, FACTS, [])
    joined = " ".join(problems)
    assert "'crucial'" in joined and "bottleneck" in joined and "engagement bait" in joined


def test_length_and_first_line():
    problems = check_draft("Short post.\n\n#a", SOLO_SIM, FACTS, [])
    assert any(p.startswith("length") for p in problems)
    long_first = _post("I used simulated data.", first="I " + "really " * 30 + "wrote checks.")
    assert any("first line" in p for p in check_draft(long_first, SOLO_SIM, FACTS, []))


def test_repeated_opener_and_near_duplicate_are_caught():
    post = _post("I built it on simulated data.")
    history = [{"date": "2026-10-19", "text": post}]
    problems = check_draft(post, SOLO_SIM, FACTS, history)
    assert any("opening line repeats" in p for p in problems)
    assert any("too similar" in p for p in problems)
    assert body_similarity(post, "something entirely different about dbt tests and warehouses") < 0.05


def test_hashtags_collected_on_one_line():
    text = "Body line.\n\n#DataEngineering\n#AWS\n#Airflow\n#More"
    assert tidy_hashtags(text) == "Body line.\n\n#DataEngineering #AWS"


def test_comparison_with_like_this_is_not_bait_but_asking_for_likes_is():
    from app.services.post_rules import ENGAGEMENT_BAIT

    assert not ENGAGEMENT_BAIT.search("If you've built scoring like this, how did you decide when rules were enough?")
    for bait in ("Like this post if it helped", "Share if you agree", "Follow me for more", "Comment below"):
        assert ENGAGEMENT_BAIT.search(bait), bait


def test_a_list_of_steps_is_sent_back():
    # The 2026-10-23 draft: three paragraphs opening with "I", two in a row with "I built", 149 words.
    steps = "\n\n".join(["A month filter pruned 60k simulated postings down to one partition.", "I built this project to learn how the system fits.",
                         "I built an external table over raw files.", "I ran a repair command.", "#DataEngineering #PySpark"])
    problems = check_draft(steps, SOLO_SIM, FACTS + " month filter partition external table repair", [])
    assert any("paragraphs start with 'I'" in p for p in problems)
    assert any("in a row open with 'i built'" in p for p in problems)
    assert any("must be at least 150" in p for p in problems)


def test_the_approved_examples_pass_the_shape_rules():
    from pathlib import Path
    text = (Path(__file__).resolve().parents[1] / "data" / "approved_posts.txt").read_text(encoding="utf-8")
    posts = [block.split("---", 1)[1].strip() for block in text.split("--- EXAMPLE")[1:]]
    assert len(posts) == 2
    for post in posts:
        shape = [p for p in check_draft(post, {"kind": "project", "solo": True}, post, []) if "'I'" in p or "in a row" in p or "words" in p]
        assert shape == []
