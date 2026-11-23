"""How each post did, measured at a known age, so the learner compares like with like.

LinkedIn gives post analytics through its API only to registered companies (Community Management API), so the numbers come from the
owner's own analytics: the export file (Analytics > Export, XLSX or CSV) or numbers read from the post's analytics page. Each
measurement is stored with the post's age in days: about 57% of a post's 30-day impressions arrive in 24 hours and 89% in 7 days
(ContentIn, 427 posts), so the 7-day number is the one compared, and a number read at another age is kept but marked as such.

data/post_metrics.json is a list of {"date", "measured_at", "age_days", "impressions", "reactions", "comments", "reposts", "source"};
"date" is the post's date in post_history.json, which ties a measurement to its post."""

import csv
import io
import json
import os
import re
import statistics
from datetime import date, datetime

METRICS_PATH = "data/post_metrics.json"
COMPARE_AGE = 7
# A measurement at 5-45 days stands in for the 7-day number, the one nearest 7 preferred. A late one overstates it by at most about
# 12% (89% of 30-day impressions are in by day 7), small next to the post-to-post spread (40-300).
AGE_WINDOW = (5, 45)
DUE_WINDOW = (7, 10)
BASELINE_POSTS = 12

_FIELDS = {
    "impressions": r"^impressions?$|^views?$",
    "reactions": r"^reactions?$|^likes?$",
    "comments": r"^comments?$",
    "reposts": r"^reposts?$|^shares?$",
    "date": r"publish|created|^date$|posted",
    "url": r"url|link",
    "text": r"title|text|commentary|content",
}


def load(path: str | None = None) -> list[dict]:
    path = path or METRICS_PATH
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save(rows: list[dict], path: str | None = None) -> None:
    path = path or METRICS_PATH
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)
        f.write("\n")


def _day(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value or "").strip()
    m = re.match(r"(\d{4}-\d{2}-\d{2})", text)
    if m:
        return date.fromisoformat(m.group(1))
    for candidate in (text, text.split(" ")[0]):
        for fmt in ("%m/%d/%Y", "%m/%d/%y", "%b %d, %Y", "%B %d, %Y"):
            try:
                return datetime.strptime(candidate, fmt).date()
            except ValueError:
                continue
    return None


def _int(value) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(str(value).replace(",", "").strip()))
    except ValueError:
        return None


def match_post(history: list[dict], on: date | None = None, text: str | None = None) -> dict | None:
    """The history entry a measurement belongs to: the post on that date, else the one whose opening words the text starts with."""
    if on:
        same = [h for h in history if h.get("date") == str(on)]
        if len(same) == 1:
            return same[0]
    if text:
        words = re.findall(r"[a-z0-9]+", text.lower())[:8]
        for h in history:
            if words and re.findall(r"[a-z0-9]+", (h.get("text") or "").lower())[:8] == words:
                return h
    return None


def record(rows: list[dict], post: dict, measured_at: date, impressions: int, reactions: int | None = None,
           comments: int | None = None, reposts: int | None = None, source: str = "manual") -> dict:
    """Adds one measurement (replacing an earlier one for the same post and day)."""
    posted = date.fromisoformat(post["date"])
    row = {"date": post["date"], "measured_at": str(measured_at), "age_days": (measured_at - posted).days,
           "impressions": impressions, "reactions": reactions, "comments": comments, "reposts": reposts, "source": source}
    rows[:] = [r for r in rows if not (r["date"] == row["date"] and r["measured_at"] == row["measured_at"])] + [row]
    rows.sort(key=lambda r: (r["date"], r["measured_at"]))
    return row


def _table(path: str) -> list[list]:
    if path.lower().endswith((".xlsx", ".xlsm")):
        from openpyxl import load_workbook

        wb = load_workbook(path, read_only=True, data_only=True)
        # The export has several sheets (discovery, engagement, top posts, followers); the per-post one has an impressions column.
        best = []
        for ws in wb.worksheets:
            rows = [list(r) for r in ws.iter_rows(values_only=True)]
            if any(any(re.search(_FIELDS["impressions"], str(c or "").strip(), re.I) for c in r) for r in rows[:15]):
                if len(rows) > len(best):
                    best = rows
        return best
    with open(path, encoding="utf-8-sig") as f:
        return [r for r in csv.reader(io.StringIO(f.read()))]


def import_export(path: str, history: list[dict], rows: list[dict], measured_at: date) -> tuple[int, list[str]]:
    """Reads the owner's LinkedIn analytics export and records each post it can tie to a history entry. Returns (recorded, notes);
    a row that matches no post, or a header that cannot be found, is reported, never guessed."""
    table = _table(path)
    head_i = next((i for i, r in enumerate(table[:15])
                   if any(re.search(_FIELDS["impressions"], str(c or "").strip(), re.I) for c in r)), None)
    if head_i is None:
        return 0, [f"no impressions column found in {os.path.basename(path)}"]
    header = [str(c or "").strip() for c in table[head_i]]
    col = {}
    for key, pattern in _FIELDS.items():
        for i, name in enumerate(header):
            if key not in col and re.search(pattern, name, re.I):
                col[key] = i
    notes, done = [], 0
    for r in table[head_i + 1:]:
        if not any(r):
            continue
        cell = lambda k: r[col[k]] if k in col and col[k] < len(r) else None  # noqa: E731
        impressions = _int(cell("impressions"))
        if impressions is None:
            continue
        post = match_post(history, _day(cell("date")), str(cell("text") or ""))
        if post is None:
            notes.append(f"no post matched: {cell('date')} {str(cell('text') or cell('url') or '')[:60]}")
            continue
        record(rows, post, measured_at, impressions, _int(cell("reactions")), _int(cell("comments")), _int(cell("reposts")),
               source="export")
        done += 1
    return done, notes


def seven_day(rows: list[dict], post_date: str) -> dict | None:
    """The measurement standing for a post's 7-day number: the one closest to 7 days inside the 5-10 day window."""
    near = [r for r in rows if r["date"] == post_date and AGE_WINDOW[0] <= r["age_days"] <= AGE_WINDOW[1]]
    return min(near, key=lambda r: abs(r["age_days"] - COMPARE_AGE)) if near else None


def relative_reach(rows: list[dict], history: list[dict]) -> list[dict]:
    """Each post's 7-day impressions divided by the median of the BASELINE_POSTS posts before it (the account's own recent level, so a
    platform-wide drop or follower growth does not read as a post effect). Posts without a 7-day number are listed with None."""
    out, before = [], []
    for h in sorted(history, key=lambda e: e["date"]):
        m = seven_day(rows, h["date"])
        base = statistics.median(before[-BASELINE_POSTS:]) if len(before) >= 3 else None
        ratio = round(m["impressions"] / base, 2) if m and base else None
        out.append({"date": h["date"], "subject": h.get("subject"), "media": h.get("media"), "seven_day": m["impressions"] if m else None,
                    "baseline": base, "ratio": ratio})
        if m:
            before.append(m["impressions"])
    return out


def due_for_measurement(rows: list[dict], history: list[dict], today: date) -> list[dict]:
    """Posts 7-10 days old with no 7-day number yet: the ones to read this week."""
    return [h for h in history if DUE_WINDOW[0] <= (today - date.fromisoformat(h["date"])).days <= DUE_WINDOW[1]
            and not any(r["date"] == h["date"] and DUE_WINDOW[0] <= r["age_days"] <= DUE_WINDOW[1] for r in rows)]


# --- Whether posting helps the job search (plan step 10) ---------------------------------------------------------------------------
# Impressions are the learner's reward, but the goal is interviews: a weekly snapshot of the dashboard's profile and search numbers,
# with recruiter contacts counted by hand, is read next to posting activity as a trend (too sparse to credit single posts).
OUTCOMES_PATH = "data/outcomes.json"
OUTCOME_FIELDS = ("profile_viewers_90d", "search_appearances_week", "followers", "post_impressions_7d", "recruiter_messages_week",
                  "interview_invites_week")


def record_outcome(rows: list[dict], on: date, **values) -> dict:
    """Adds (or replaces) the snapshot for one day; values are the dashboard numbers read that morning."""
    row = {"date": str(on), **{k: values.get(k) for k in OUTCOME_FIELDS}}
    rows[:] = [r for r in rows if r["date"] != row["date"]] + [row]
    rows.sort(key=lambda r: r["date"])
    return row
