"""Stories: the material a post is written from.

A post written from a project's resume bullets reads as a list of facts, and its image (drawn from the same bullets) ends up about
something else. The posts the owner approved each tell one measured test instead: a question, how it was tested, the numbers, and
the decision that followed. A story holds exactly that, taken from the project's own repository documents (README and docs/*.md), and
every number in it must appear in that source. The post is written from one story, and its image charts that story's numbers, so text
and image describe the same thing.

data/stories.json is filled by refill(): when fewer than MIN_UNUSED stories are left, the documents of projects without stories are read
and stories are extracted from them. A story is used once; one rejected twice by the owner is not offered again.
"""

import json
import os
import re

import httpx

from app.services.post_rules import numbers_in, unsupported_numbers
from app.utils.logging import logger

STORIES_PATH = os.path.join("data", "stories.json")
FEEDBACK_PATH = os.path.join("data", "feedback.json")
MIN_UNUSED = 4
MAX_SUBJECTS_PER_REFILL = 2
MAX_DOC_CHARS = 24000


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


def pick_story(items: list[dict], history: list[dict], stories: list[dict] | None = None,
               feedback: list[dict] | None = None) -> tuple[dict, dict] | None:
    """The unused story whose subject was posted about least recently; ties go to the profile's own order (most recent work first)."""
    by_title = {i["title"]: i for i in items}
    recent = [h.get("subject") for h in history]

    def last_posted(subject: str) -> int:
        return max((n for n, s in enumerate(recent) if s == subject), default=-1)

    order = {t: n for n, t in enumerate(by_title)}
    candidates = [s for s in unused(history, stories, feedback) if s["subject"] in by_title]
    if not candidates:
        return None
    best = min(candidates, key=lambda s: (last_posted(s["subject"]), order[s["subject"]]))
    return best, by_title[best["subject"]]


# --- Filling the bank from the project's own documents -------------------------------------------------------------------------------

def _repo(github_url: str) -> str | None:
    m = re.match(r"https?://github\.com/([^/]+/[^/#?]+)", github_url or "")
    return m.group(1).removesuffix(".git") if m else None


async def fetch_docs(github_url: str) -> tuple[str, list[str]]:
    """README.md and docs/*.md of a public repository, with the URLs they came from."""
    repo = _repo(github_url)
    if not repo:
        return "", []
    headers = {"Accept": "application/vnd.github+json"}
    if os.getenv("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {os.getenv('GITHUB_TOKEN')}"
    texts, sources = [], []
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        paths = ["README.md"]
        try:
            resp = await client.get(f"https://api.github.com/repos/{repo}/contents/docs", headers=headers)
            if resp.status_code == 200:
                paths += [f["path"] for f in resp.json() if f.get("name", "").lower().endswith(".md")][:6]
        except Exception as exc:
            logger.warning("Could not list docs/ of %s: %s", repo, exc)
        for path in paths:
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

Find up to {n} separate stories in them that would each make one LinkedIn post. A story is ONE measured test or comparison: a question
the author had, how it was tested, the measured results, and the decision taken because of them. Good stories compare two or more
things with numbers (before and after, option A against option B, a rule against a model, a target against the result).
Skip anything that is only a feature list or a description of the stack.

Rules:
- Every number must be copied exactly as it appears in DOCUMENTS. Never compute, round or invent a number.
- Every result must have a short label (at most 8 words) and a value that is a number from DOCUMENTS with its unit, like "92.5%",
  "0.9 s", "43 entries".
- Give 2 to 5 results per story, and prefer results that can be compared on one chart (same unit).
- "decision" says what was chosen or changed because of the results, only as the documents state it. If the documents state no
  decision, give the plain conclusion they draw.
- "chart_title" is at most 10 words and names what the results measure.
- If the work used simulated or synthetic data, say so in "test".

Return only JSON: {{"stories": [{{"question": "...", "test": "...", "results": [{{"label": "...", "value": "..."}}], "decision": "...",
"detail": "one optional sentence of supporting detail from DOCUMENTS, or empty", "chart_title": "..."}}]}}

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
    if len(numeric) < 2:
        problems.append("fewer than 2 numeric results")
    elif len({str(r.get("value", "")).strip().lower() for r in numeric}) < 2:
        problems.append("all results are the same number, so there is nothing to compare")
    text = " ".join([str(story.get(k, "")) for k in ("question", "test", "decision", "detail", "chart_title")] +
                    [f"{r.get('label', '')} {r.get('value', '')}" for r in results])
    bad = unsupported_numbers(text, docs)
    if bad:
        problems.append(f"numbers not in the documents: {bad}")
    return problems


async def mine_subject(item: dict, settings, n: int = 3) -> list[dict]:
    from app.services.llm_service import call_llm_with_fallback

    docs, sources = await fetch_docs(item.get("github_url", ""))
    if len(docs) < 400:
        logger.info("No usable documents for %s", item["title"])
        return []
    raw = await call_llm_with_fallback(
        messages=[{"role": "user", "content": MINE_PROMPT.format(title=item["title"], n=n, docs=docs)}], settings=settings, temperature=0.2)
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    try:
        found = json.loads(raw).get("stories", [])
    except ValueError:
        logger.warning("Story extraction for %s returned no readable JSON", item["title"])
        return []
    stories = []
    for k, s in enumerate(found):
        if not isinstance(s, dict):
            continue
        problems = verify_story(s, docs)
        if problems:
            logger.info("Story %d for %s dropped: %s", k, item["title"], problems)
            continue
        slug = re.sub(r"[^a-z0-9]+", "-", item["title"].lower()).strip("-")[:40]
        stories.append({"id": f"{slug}-{len(stories) + 1}", "subject": item["title"], **{key: s[key] for key in
                        ("question", "test", "results", "decision", "chart_title")}, "detail": s.get("detail") or "",
                        "sources": sources, "simulated": bool(item.get("simulated"))})
    return stories


async def refill(items: list[dict], history: list[dict], settings, path: str | None = None) -> str:
    """Mine new stories when fewer than MIN_UNUSED are left: projects with no stories yet first, most recent work first."""
    path = path or STORIES_PATH
    stories = load_stories(path)
    left = len(unused(history, stories))
    if left >= MIN_UNUSED:
        return f"{left} stories ready"
    mined_subjects = {s["subject"] for s in stories} | {s for s in _load(path + ".tried", [])}
    todo = [i for i in items if i.get("github_url") and i["title"] not in mined_subjects][:MAX_SUBJECTS_PER_REFILL]
    added = 0
    for item in todo:
        try:
            new = await mine_subject(item, settings)
        except Exception as exc:
            logger.warning("Story extraction for %s failed: %s", item["title"], exc)
            continue
        existing = {s["id"] for s in stories}
        for s in new:
            while s["id"] in existing:
                s["id"] += "x"
            stories.append(s)
            existing.add(s["id"])
        added += len(new)
        if not new:
            _save(path + ".tried", sorted(set(_load(path + ".tried", [])) | {item["title"]}))
    _save(path, stories)
    return f"{left} stories ready, {added} new from {', '.join(i['title'] for i in todo) or 'no new project'}"
