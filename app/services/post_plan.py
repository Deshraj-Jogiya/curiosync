"""Choosing what to post about and how to open it.

Subjects are scored instead of rotated: posts work as proof of skill for recruiters already looking at the profile, so the strongest recent
data engineering and ML work should come up most, and old or thin projects drop out. Hook types rotate least-recently-used, and a
published-post history (data/post_history.json, committed by the publish job) keeps subjects, openers and bodies from repeating.
"""

import json
import os
import re
from datetime import date

from app.services.profile_source import featurable_items

NOTES_PATH = os.path.join("data", "subject_notes.json")
HISTORY_PATH = os.path.join("data", "post_history.json")

# Terms that matter for Data Engineer, ML Engineer and Analytics Engineer job descriptions. Weighted by how central they are.
ROLE_TERMS = {
    3: ["pipeline", "etl", "elt", "warehouse", "lakehouse", "dbt", "spark", "pyspark", "airflow", "snowflake", "databricks",
        "data quality", "great expectations", "dimensional", "star schema", "terraform", "delta lake", "iceberg", "orchestrat"],
    2: ["sql", "aws", "glue", "s3", "lambda", "azure", "postgres", "drift", "mlops", "mlflow", "model", "llm", "rag", "embedding",
        "fine-tun", "lora", "deployed", "production", "ci", "tests", "latency", "throughput"],
    1: ["python", "dashboard", "tableau", "power bi", "api", "docker", "kubernetes", "anomaly", "forecast"],
}

# Opening styles. "needs" names a fact pattern that must exist before the style can be used, so a "mistake" opener is never invented.
HOOK_TYPES = {
    "measured_result": {"needs": r"\d", "instruction": "Open with the single most concrete measured result from FEATURED, stated plainly."},
    "decision_cost": {"needs": None, "instruction": "Open with one design decision you made in FEATURED and what it cost or ruled out."},
    "bug_found": {"needs": r"found and fixed|fixed .*bug|bug|surfaced only", "instruction": "Open with a specific problem you found and fixed in FEATURED, named exactly as the facts describe it."},
    "surprise": {"needs": r"discovered|not assumed|instead of|rather than|than expected|only by running", "instruction": "Open with something that turned out differently from the obvious approach, taken from FEATURED."},
    "claim": {"needs": None, "instruction": "Open with a short, specific opinion about building this kind of system that FEATURED directly supports."},
}

NEWS_EVERY_N_POSTS = 6


def _load_json(path: str, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def load_notes() -> dict:
    return _load_json(NOTES_PATH, {})


def load_history() -> list[dict]:
    return _load_json(HISTORY_PATH, [])


def append_history(entry: dict, path: str = HISTORY_PATH) -> None:
    history = _load_json(path, [])
    history.append(entry)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


def _note_for(title: str, notes: dict) -> dict:
    t = title.lower()
    for key, value in notes.items():
        if not key.startswith("_") and t.startswith(key.lower()):
            return value
    return {}


def _end_year(dates: str) -> int:
    if re.search(r"present", dates or "", re.IGNORECASE):
        return date.today().year
    years = [int(y) for y in re.findall(r"(?:19|20)\d\d", dates or "")]
    return max(years) if years else 0


def enrich(item: dict, notes: dict) -> dict:
    note = _note_for(item["title"], notes)
    facts_text = " ".join(item["facts"])
    out = dict(item)
    out["context"] = note.get("context", "Personal portfolio project" if item["kind"] == "project" else "")
    out["simulated"] = note.get("simulated", bool(re.search(r"simulat|synthetic", facts_text, re.IGNORECASE)))
    out["solo"] = note.get("solo", True)
    out["notes"] = list(note.get("notes", []))
    out["exclude"] = bool(note.get("exclude", False))
    out["end_year"] = _end_year(item.get("dates", ""))
    return out


def candidates(profile: dict, kind: str, notes: dict) -> list[dict]:
    min_year = notes.get("_settings", {}).get("min_year", 0)
    items = [enrich(i, notes) for i in featurable_items(profile, kind)]
    return [i for i in items if not i["exclude"] and i["end_year"] >= min_year]


def relevance(item: dict) -> int:
    text = " ".join(item["facts"]).lower()
    return sum(weight for weight, terms in ROLE_TERMS.items() for term in terms if term in text)


def depth(item: dict) -> int:
    return min(len(re.findall(r"\d", " ".join(item["facts"]))), 20)


def score(item: dict, history: list[dict], today: date) -> float:
    s = relevance(item) * 1.0 + depth(item) * 0.5
    age = max(0, today.year - item["end_year"])
    s -= age * 6
    # Least recently used: a subject posted within the last 6 posts is pushed down hard, within the last 12 a little.
    recent = [h.get("subject") for h in history]
    if item["title"] in recent[-6:]:
        s -= 100
    elif item["title"] in recent[-12:]:
        s -= 15
    if item["simulated"]:
        s -= 4
    return s


def pick_subject(profile: dict, fmt: str, history: list[dict], today: date, notes: dict | None = None) -> dict:
    notes = load_notes() if notes is None else notes
    if fmt == "project_spotlight":
        pool = candidates(profile, "project", notes)
    elif fmt == "decision":
        pool = [i for i in candidates(profile, "project", notes) + candidates(profile, "experience", notes) if i["notes"]]
        pool = pool or candidates(profile, "project", notes) + candidates(profile, "experience", notes)
    else:
        pool = candidates(profile, "project", notes) + candidates(profile, "experience", notes)
    if not pool:
        raise ValueError("no eligible subjects")
    return max(pool, key=lambda i: score(i, history, today))


def pick_hook(item: dict, history: list[dict]) -> str:
    facts = " ".join(item["facts"] + item.get("notes", []))
    usable = [h for h, spec in HOOK_TYPES.items() if spec["needs"] is None or re.search(spec["needs"], facts, re.IGNORECASE)]
    last_used = {h: -1 for h in usable}
    for idx, past in enumerate(history):
        if past.get("hook_type") in last_used:
            last_used[past["hook_type"]] = idx
    return min(usable, key=lambda h: (last_used[h], list(HOOK_TYPES).index(h)))


def news_allowed(history: list[dict]) -> bool:
    recent = [h.get("format") for h in history[-(NEWS_EVERY_N_POSTS - 1):]]
    return "news_take" not in recent


def matching_news(item: dict, news_items: list[dict]) -> dict | None:
    """A news item about a tool this subject actually used, or None. News posts are only written when there is a real tie."""
    from app.services.post_rules import TECH_TERMS, _term_in

    facts = " ".join(item["facts"])
    tools = [t for t in TECH_TERMS if len(t) > 3 and _term_in(t, facts)]
    for news in news_items:
        headline = f"{news.get('title', '')} {news.get('summary', '')}"
        if any(_term_in(t, headline) for t in tools):
            return news
    return None
