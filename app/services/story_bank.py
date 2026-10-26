"""Stories: the material a post is written from.

A post written from a project's resume bullets reads as a list of facts, and its image (drawn from the same bullets) ends up about
something else. The posts the owner approved each tell one measured test instead: a question, how it was tested, the numbers, and
the decision that followed. A story holds exactly that, taken from the project's own repository documents (README, FINDINGS and every
other .md in the root, docs/ and reports/), and every number in it must appear in that source. The post is written from one story, and
its image charts that story's numbers, so text and image describe the same thing.

data/stories.json is filled by refill() on every run: up to MAX_SUBJECTS_PER_REFILL projects a run, first those never read, then those
whose repository changed since it was last read (data/stories_meta.json keeps the commit each was read at), so new work in any repo
becomes new stories by itself. Every story a document supports is kept, not a fixed few, and each lists the skills it shows, so the
posts rotate across projects and skills. A story is used once; one rejected twice by the owner is not offered again. When every story
has been used, the one posted longest ago (at least REPEAT_AFTER_DAYS) may come back as a new post with a different format.
"""

import json
import os
import re
from datetime import date, timedelta

import httpx

from app.services.post_rules import numbers_in, unsupported_numbers
from app.utils.logging import logger

STORIES_PATH = os.path.join("data", "stories.json")
META_PATH = os.path.join("data", "stories_meta.json")
FEEDBACK_PATH = os.path.join("data", "feedback.json")
MAX_SUBJECTS_PER_REFILL = 3
MAX_DOC_CHARS = 60000
# Groq's free tier takes about 7,000-8,000 input tokens a minute per model, so documents are read in pieces of this size (about
# 3,500 tokens), one file or part of a file at a time, FINDINGS first. Every number is still checked against all the documents.
CHUNK_CHARS = 14000
MAX_CHUNKS_PER_PROJECT = 4
MAX_STORIES_PER_PROJECT = 12
MIN_RESULTS = 3
REPEAT_AFTER_DAYS = 180
RECENT_POSTS_FOR_SKILLS = 10
# Mining reads whole documents (thousands of tokens each); it pauses while this many stories are waiting, to keep the free daily
# allowance for writing posts. Changed repositories are still read once the bank drops below it.
HEALTHY_BANK = 20


def _load(path: str, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def _save(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_stories(path: str | None = None) -> list[dict]:
    return _load(path or STORIES_PATH, [])


def load_feedback(path: str | None = None) -> list[dict]:
    return _load(path or FEEDBACK_PATH, [])


def add_feedback(entry: dict, path: str | None = None) -> None:
    items = load_feedback(path)
    items.append(entry)
    _save(path or FEEDBACK_PATH, items)


def story_text(story: dict) -> str:
    lines = [f"Question: {story['question']}", f"How it was tested: {story['test']}", "Results:"]
    lines += [f"- {r['label']}: {r['value']}" for r in story["results"]]
    lines.append(f"Decision: {story['decision']}")
    if story.get("detail"):
        lines.append(f"Detail: {story['detail']}")
    return "\n".join(lines)


def _rejections(story_id: str, feedback: list[dict]) -> int:
    return sum(1 for f in feedback if f.get("story_id") == story_id)


def unused(history: list[dict], stories: list[dict] | None = None, feedback: list[dict] | None = None) -> list[dict]:
    """Stories not yet posted (or waiting in the approved queue, which counts as history) and not rejected twice."""
    stories = load_stories() if stories is None else stories
    feedback = load_feedback() if feedback is None else feedback
    taken = {h.get("story_id") for h in history}
    return [s for s in stories if s["id"] not in taken and _rejections(s["id"], feedback) < 2]


def _skills_recently_featured(history: list[dict], stories: list[dict]) -> set[str]:
    by_id = {x["id"]: x for x in stories}
    recent = [h for h in history if h.get("story_id")][-RECENT_POSTS_FOR_SKILLS:]
    return {k.lower() for h in recent for k in by_id.get(h["story_id"], {}).get("skills", [])}


def pick_story(items: list[dict], history: list[dict], stories: list[dict] | None = None,
               feedback: list[dict] | None = None, today: date | None = None) -> tuple[dict, dict] | None:
    """The unused story whose project was posted about least recently; among a project's stories, the one showing the most skills not
    featured in the last posts; ties go to the profile's own order (most recent work first). With nothing unused, the story posted
    longest ago (at least REPEAT_AFTER_DAYS) comes back, marked as a repeat so it is written in a different format."""
    stories = load_stories() if stories is None else stories
    feedback = load_feedback() if feedback is None else feedback
    by_title = {i["title"]: i for i in items}
    recent = [h.get("subject") for h in history]
    featured = _skills_recently_featured(history, stories)

    def last_posted(subject: str) -> int:
        return max((n for n, s in enumerate(recent) if s == subject), default=-1)

    def new_skills(story: dict) -> int:
        return len({k.lower() for k in story.get("skills", [])} - featured)

    order = {t: n for n, t in enumerate(by_title)}
    candidates = [s for s in unused(history, stories, feedback) if s["subject"] in by_title]
    if candidates:
        best = min(candidates, key=lambda s: (last_posted(s["subject"]), -new_skills(s), order[s["subject"]]))
        return best, by_title[best["subject"]]

    today = today or date.today()
    posted_on = {}
    for h in history:
        if h.get("story_id") and h.get("date"):
            posted_on[h["story_id"]] = max(posted_on.get(h["story_id"], ""), h["date"])
    cutoff = str(today - timedelta(days=REPEAT_AFTER_DAYS))
    old = [s for s in stories if s["subject"] in by_title and posted_on.get(s["id"], "9999") <= cutoff
           and _rejections(s["id"], feedback) < 2]
    if not old:
        return None
    best = min(old, key=lambda s: posted_on[s["id"]])
    return {**best, "repeat_of": posted_on[best["id"]]}, by_title[best["subject"]]


# --- Filling the bank from the project's own documents -------------------------------------------------------------------------------

def _repo(github_url: str) -> str | None:
    m = re.match(r"https?://github\.com/([^/]+/[^/#?]+)", github_url or "")
    return m.group(1).removesuffix(".git") if m else None


async def head_sha(github_url: str) -> str | None:
    repo = _repo(github_url)
    if not repo:
        return None
    headers = {"Accept": "application/vnd.github+json"}
    if os.getenv("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {os.getenv('GITHUB_TOKEN')}"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(f"https://api.github.com/repos/{repo}/commits/HEAD", headers=headers)
        return resp.json().get("sha") if resp.status_code == 200 else None
    except Exception as exc:
        logger.warning("Could not read the latest commit of %s: %s", repo, exc)
        return None


def _doc_rank(path: str) -> int:
    name = path.lower()
    if "findings" in name:
        return 0
    if name == "readme.md":
        return 1
    if name.startswith(("docs/", "reports/")):
        return 2
    return 3


async def fetch_docs(github_url: str) -> tuple[str, list[str]]:
    """Every .md in the repository root, docs/ and reports/ (FINDINGS first, then README), with the URLs they came from."""
    repo = _repo(github_url)
    if not repo:
        return "", []
    headers = {"Accept": "application/vnd.github+json"}
    if os.getenv("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {os.getenv('GITHUB_TOKEN')}"
    texts, sources, paths = [], [], []
    skip = ("license", "changelog", "code_of_conduct", "security", "contributing")
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        for folder in ("", "docs", "reports"):
            try:
                resp = await client.get(f"https://api.github.com/repos/{repo}/contents/{folder}", headers=headers)
            except Exception as exc:
                logger.warning("Could not list %s/%s: %s", repo, folder or "(root)", exc)
                continue
            if resp.status_code == 200 and isinstance(resp.json(), list):
                paths += [f["path"] for f in resp.json() if f.get("type") == "file" and f.get("name", "").lower().endswith(".md")
                          and not f["name"].lower().startswith(skip)]
        if not paths:
            paths = ["README.md"]
        for path in sorted(set(paths), key=lambda x: (_doc_rank(x), x)):
            try:
                resp = await client.get(f"https://raw.githubusercontent.com/{repo}/HEAD/{path}")
            except Exception as exc:
                logger.warning("Could not read %s/%s: %s", repo, path, exc)
                continue
            if resp.status_code == 200 and resp.text.strip():
                texts.append(f"# FILE: {path}\n{resp.text}")
                sources.append(f"https://github.com/{repo}/blob/HEAD/{path}")
    return "\n\n".join(texts)[:MAX_DOC_CHARS], sources


MINE_PROMPT = """Below are the repository documents of a project by Deshraj Jogiya, "{title}".

Find EVERY separate story in them (up to {n}) that would make one LinkedIn post: do not stop at the first few, and look through all
files, including findings, evaluations, benchmarks and tables. A story is ONE measured test or comparison: a question
the author had, how it was tested, the measured results, and the decision taken because of them. Good stories compare two or more
things with numbers (before and after, option A against option B, a rule against a model, a target against the result).
Skip anything that is only a feature list or a description of the stack.

Rules:
- Every number must be copied exactly as it appears in DOCUMENTS. Never compute, round or invent a number.
- Every result must have a short label (at most 8 words) and a value that is a number from DOCUMENTS with its unit, like "92.5%",
  "0.9 s", "43 entries".
- Every result must be an outcome of the test (accuracy, latency, rows read, cost, errors found), never a description of the setup
  (dataset size, number of companies, number of reducers or partitions written). If a test has fewer than 3 outcomes, leave it out.
- Give 3 to 6 results per story. When the story compares options, give each option the same metrics (accuracy of A and of B,
  latency of A and of B), so they can be compared on one chart.
- "decision" says what was chosen or changed because of the results, only as the documents state it. If the documents state no
  decision, give the plain conclusion they draw.
- "chart_title" is at most 10 words and names what the results measure.
- If the work used simulated or synthetic data, say so in "test".
- "skills" lists the tools, languages and techniques this one test used, each written exactly as DOCUMENTS write it (for example
  "XGBoost", "MLflow", "Isolation Forest", "dbt", "partition pruning"). At most 6.
- Two stories must not be the same test told twice.
- "series" (optional) holds the data behind the best chart for this story, ONLY when DOCUMENTS contain every number in it:
  * "line": a measure along an ordered axis (days, epochs, entries opened, thresholds), 1 or 2 named series of at least 3 points:
    {{"type": "line", "title": "...", "x_label": "...", "y_label": "...", "points": [{{"x": "...", "y": "...", "series": "name"}}]}}
  * "scatter": 3 or more options each measured on two things (accuracy against size, precision against recall):
    {{"type": "scatter", "title": "...", "x_label": "...", "y_label": "...", "points": [{{"label": "...", "x": "...", "y": "..."}}]}}
  * "before_after": up to 4 measures that changed (7.5 s to 0.9 s, 22 of 26 to 25 of 26):
    {{"type": "before_after", "title": "...", "points": [{{"label": "...", "before": "...", "after": "..."}}]}}
  Leave "series" out when none of these fits; the results alone are then charted.

Return only JSON: {{"stories": [{{"question": "...", "test": "...", "results": [{{"label": "...", "value": "..."}}], "decision": "...",
"detail": "one optional sentence of supporting detail from DOCUMENTS, or empty", "chart_title": "...", "skills": ["..."],
"series": {{...}} or omit}}]}}

DOCUMENTS:
{docs}
"""


def verify_story(story: dict, docs: str) -> list[str]:
    problems = []
    for key in ("question", "test", "decision", "chart_title"):
        if not str(story.get(key, "")).strip():
            problems.append(f"missing {key}")
    results = story.get("results") or []
    numeric = [r for r in results if numbers_in(str(r.get("value", "")))]
    if len(numeric) < MIN_RESULTS:
        # Two numbers make a thin story: the model pads it with arithmetic of its own and claims the documents never make.
        problems.append(f"fewer than {MIN_RESULTS} numeric results")
    elif len({str(r.get("value", "")).strip().lower() for r in numeric}) < 2:
        problems.append("all results are the same number, so there is nothing to compare")
    text = " ".join([str(story.get(k, "")) for k in ("question", "test", "decision", "detail", "chart_title")] +
                    [f"{r.get('label', '')} {r.get('value', '')}" for r in results])
    bad = unsupported_numbers(text, docs)
    if bad:
        problems.append(f"numbers not in the documents: {bad}")
    return problems


def verify_series(series, docs: str) -> list[str]:
    """Problems with a story's chart data; a story whose series fails keeps its results and loses only the series."""
    if not isinstance(series, dict) or series.get("type") not in ("line", "scatter", "before_after"):
        return ["no usable series type"]
    points = series.get("points")
    if not isinstance(points, list) or not points or not all(isinstance(p, dict) for p in points):
        return ["no points"]
    kind = series["type"]
    if kind == "before_after":
        if len(points) > 4 or any(not (str(p.get("before", "")).strip() and str(p.get("after", "")).strip()) for p in points):
            return ["before and after values missing"]
        values = [f"{p['before']} {p['after']}" for p in points]
    else:
        if any(not numbers_in(str(p.get("x", ""))) or not numbers_in(str(p.get("y", ""))) for p in points):
            return ["a point without numbers"]
        groups = {}
        for p in points:
            groups.setdefault(p.get("series") or p.get("label") or "", []).append(p)
        if kind == "line" and (len(groups) > 2 or any(len(g) < 3 for g in groups.values())):
            return ["a line needs 1-2 series of 3+ points"]
        if kind == "scatter" and len(points) < 3:
            return ["a scatter needs 3+ points"]
        values = [f"{p['x']} {p['y']}" for p in points]
    bad = unsupported_numbers(" ".join(values), docs)
    return [f"series numbers not in the documents: {bad}"] if bad else []


def _same_test(a: dict, b: dict) -> bool:
    """Two stories with mostly the same result numbers are the same test told twice."""
    na = {v for r in a["results"] for v in numbers_in(str(r["value"]))}
    nb = {v for r in b["results"] for v in numbers_in(str(r["value"]))}
    return bool(na and nb) and len(na & nb) / min(len(na), len(nb)) >= 0.6


def parse_stories(raw: str) -> list | None:
    """The "stories" list from a model reply, tolerating code fences and text around the JSON. None when no JSON can be read."""
    raw = re.sub(r"^```(?:json)?|```$", "", (raw or "").strip(), flags=re.MULTILINE).strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        found = json.loads(raw[start:end + 1]).get("stories", [])
    except (ValueError, AttributeError):
        return None
    return found if isinstance(found, list) else None


def doc_chunks(docs: str, size: int = CHUNK_CHARS) -> list[str]:
    """The documents split at file boundaries (and inside a long file at paragraph breaks) into pieces of at most `size` characters."""
    files = [f for f in re.split(r"(?=^# FILE: )", docs, flags=re.MULTILINE) if f.strip()]
    chunks: list[str] = []
    for f in files:
        while len(f) > size:
            cut = f.rfind("\n\n", 0, size)
            cut = cut if cut > size // 2 else size
            chunks.append(f[:cut])
            f = f[cut:]
        if chunks and len(chunks[-1]) + len(f) <= size:
            chunks[-1] += "\n\n" + f
        else:
            chunks.append(f)
    return chunks


async def mine_subject(item: dict, settings, n: int = MAX_STORIES_PER_PROJECT) -> list[dict]:
    from app.services.llm_service import call_llm_with_fallback

    docs, sources = await fetch_docs(item.get("github_url", ""))
    if len(docs) < 400:
        logger.info("No usable documents for %s", item["title"])
        return []
    found = []
    for piece in doc_chunks(docs)[:MAX_CHUNKS_PER_PROJECT]:
        prompt = MINE_PROMPT.format(title=item["title"], n=n, docs=piece) + "\nReturn only the JSON object, nothing else."
        # One retry at temperature 0 when the reply has no readable JSON; both tries use the mining models, so mining never spends the
        # allowance the writing models need.
        for attempt, temperature in enumerate((0.2, 0.0), 1):
            try:
                raw = await call_llm_with_fallback(messages=[{"role": "user", "content": prompt}], settings=settings,
                                                   temperature=temperature, tier="mine")
            except Exception as exc:
                logger.warning("Story extraction for %s failed on one part: %s", item["title"], str(exc)[:200])
                break
            part = parse_stories(raw)
            if part is not None:
                found += part
                break
            logger.warning("Story extraction for %s (try %d) returned no readable JSON: %r", item["title"], attempt, (raw or "")[:200])
    stories = []
    for k, s in enumerate(found):
        if not isinstance(s, dict):
            continue
        problems = verify_story(s, docs)
        if problems:
            logger.info("Story %d for %s dropped: %s", k, item["title"], problems)
            continue
        slug = re.sub(r"[^a-z0-9]+", "-", item["title"].lower()).strip("-")[:40]
        skills = [k for k in s.get("skills") or [] if isinstance(k, str) and k.strip() and k.lower() in docs.lower()][:6]
        story = {"id": f"{slug}-{len(stories) + 1}", "subject": item["title"], **{key: s[key] for key in
                 ("question", "test", "results", "decision", "chart_title")}, "detail": s.get("detail") or "",
                 "skills": skills, "sources": sources, "simulated": bool(item.get("simulated"))}
        series_problems = verify_series(s.get("series"), docs) if s.get("series") else ["none"]
        if not series_problems:
            story["series"] = s["series"]
        elif s.get("series"):
            logger.info("Series for story %d of %s dropped: %s", k, item["title"], series_problems)
        if any(_same_test(story, kept) for kept in stories):
            continue
        stories.append(story)
    return stories


async def refill(items: list[dict], history: list[dict], settings, path: str | None = None, meta_path: str | None = None,
                 reread_without_charts: bool = False) -> str:
    """Read up to MAX_SUBJECTS_PER_REFILL projects this run: never-read ones first (most recent work first), then ones whose repository
    has new commits. New stories that repeat a test already in the bank are skipped."""
    path, meta_path = path or STORIES_PATH, meta_path or META_PATH
    stories = load_stories(path)
    meta = _load(meta_path, {})
    for title in _load(path + ".tried", []):  # the old list of projects read without result
        meta.setdefault(title, {"sha": None})
    left = len(unused(history, stories))
    if left >= HEALTHY_BANK:
        return f"{left} stories ready"

    never = [i for i in items if i.get("github_url") and i["title"] not in meta and not any(x["subject"] == i["title"] for x in stories)]
    if reread_without_charts:
        # Projects whose stories were mined before chart data existed, read again so their stories gain a series.
        never = [i for i in items if any(x["subject"] == i["title"] and not x.get("series") for x in stories)] + never
    todo, shas = never[:MAX_SUBJECTS_PER_REFILL], {}
    if len(todo) < MAX_SUBJECTS_PER_REFILL:
        for i in items:
            if len(todo) >= MAX_SUBJECTS_PER_REFILL:
                break
            if not i.get("github_url") or i in todo:
                continue
            sha = await head_sha(i["github_url"])
            if sha and meta.get(i["title"], {}).get("sha") != sha:
                todo.append(i)
                shas[i["title"]] = sha

    added = 0
    for item in todo:
        try:
            new = await mine_subject(item, settings)
        except Exception as exc:
            logger.warning("Story extraction for %s failed: %s", item["title"], exc)
            continue
        existing = {x["id"] for x in stories}
        for st in new:
            same = next((x for x in stories if x["subject"] == st["subject"] and _same_test(st, x)), None)
            if same:
                # Read again: an existing story gains the chart data, skills and sources it was missing; its id stays.
                for key in ("series", "skills", "sources"):
                    if st.get(key) and not same.get(key):
                        same[key] = st[key]
                continue
            while st["id"] in existing:
                st["id"] += "x"
            stories.append(st)
            existing.add(st["id"])
            added += 1
        meta[item["title"]] = {"sha": shas.get(item["title"]) or await head_sha(item["github_url"]), "read_on": str(date.today()),
                               "stories": len(new)}
    _save(path, stories)
    _save(meta_path, meta)
    return f"{left} stories ready, {added} new from {', '.join(i['title'] for i in todo) or 'no changed project'}"
