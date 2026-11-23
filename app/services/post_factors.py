"""The factors a post is compared on, defined once (plan step 6), so the learner later compares like with like.

Topic is never a factor: what a post is about is decided by supply and rotation, so a strong project cannot crowd out the rest. Each
factor below has a fixed list of levels with a one-line definition; a post's levels are read from what the pipeline already records,
never guessed afterwards.

Two limits found on 2026-11-22, before any learning: the angle is set by the weekday (Mon spotlight, Wed lesson, Fri decision), so an
angle effect cannot be told from a day effect until some angle runs on another day; and 22 of 28 queued posts open with a measured
result, so the hook has almost nothing to compare. `balance` reports both, so they are seen before a learner reads anything into them.
"""

from datetime import date, datetime

FACTORS = {
    "media": {
        "image": "one chart or card",
        "document": "a PDF shown as a swipeable carousel",
        "text": "no media",
    },
    "angle": {
        "project_spotlight": "what the project does and the one result that shows it works",
        "lesson": "what the work taught, with the test that showed it",
        "decision": "a choice made, what it cost and what it bought",
        "news_take": "a current event read through the owner's own work",
    },
    "hook": {
        "measured_result": "opens with a result set against what it was compared with",
        "decision_cost": "opens with a design decision and what it ruled out",
        "bug_found": "opens with a problem found and fixed",
        "surprise": "opens with something that turned out differently from the obvious approach",
        "claim": "opens with a specific opinion the work supports",
    },
    "slot": {
        "morning": "went out before noon Arizona time (the owner-time publish)",
        "afternoon": "went out at noon or later (GitHub's late scheduled run)",
    },
}
ARIZONA_UTC_OFFSET = -7  # Arizona keeps standard time all year
DOMINANT_SHARE = 0.6


def _slot(posted_at: str | None) -> str | None:
    if not posted_at:
        return None
    hour = (datetime.fromisoformat(posted_at).hour + ARIZONA_UTC_OFFSET) % 24
    return "morning" if hour < 12 else "afternoon"


def tag(entry: dict) -> dict:
    """The post's level on each factor; None where the record does not say (older posts have no posting time)."""
    levels = {"media": entry.get("media"), "angle": entry.get("format"), "hook": entry.get("hook_type"),
              "slot": _slot(entry.get("posted_at"))}
    return {k: (v if v in FACTORS[k] else None) for k, v in levels.items()}


def balance(entries: list[dict]) -> list[str]:
    """Plain warnings about factors the posts cannot yet compare: one level taking most posts, or a factor that moves in step with the
    weekday."""
    notes = []
    tagged = [tag(e) for e in entries]
    for factor in FACTORS:
        seen = [t[factor] for t in tagged if t[factor]]
        if len(seen) < 4:
            continue
        top = max(set(seen), key=seen.count)
        if seen.count(top) / len(seen) > DOMINANT_SHARE:
            notes.append(f"{factor}: {seen.count(top)} of {len(seen)} posts are '{top}', too few of the others to compare")
        days = {}
        for e, t in zip(entries, tagged):
            if t[factor] and e.get("date"):
                days.setdefault(t[factor], set()).add(date.fromisoformat(e["date"]).weekday())
        if len(days) > 1 and all(len(d) == 1 for d in days.values()) and len(set().union(*days.values())) == len(days):
            notes.append(f"{factor}: each level runs on its own weekday, so its effect cannot be told from the day's")
    return notes
