"""Career facts for posts, read from the live portfolio's projects.json.

The portfolio's projects.json is regenerated from the master profile every time the profile changes, so reading it at run time keeps every
post in step with the resume and the site. There is deliberately no bundled fallback copy: a stale copy is how hardcoded facts drifted from
the profile before. If the file cannot be read, no post is drafted that day.
"""

import html
import re

import httpx

from app.services.github_service import CONFIDENTIAL_REPO_NAMES

PROFILE_URL = "https://deshraj-jogiya.github.io/projects.json"

# Projects never offered as post subjects: team work (see github_service) and CurioSync itself, which publishes these posts.
_EXCLUDED_PROJECT_PREFIXES = ("curiosync",)


class ProfileUnavailable(RuntimeError):
    pass


async def load_profile(url: str = PROFILE_URL) -> dict:
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url)
        resp.raise_for_status()
        profile = resp.json()
    except Exception as exc:
        raise ProfileUnavailable(f"could not read {url}: {exc}") from exc
    for key in ("title", "summary", "experience", "projects"):
        if not profile.get(key):
            raise ProfileUnavailable(f"{url} has no '{key}'")
    return profile


def plain(text: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", text or "")).strip()


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _is_excluded(project: dict) -> bool:
    slug = _slug(project.get("name", ""))
    return slug in CONFIDENTIAL_REPO_NAMES or slug.startswith(_EXCLUDED_PROJECT_PREFIXES)


def featurable_items(profile: dict, kind: str) -> list[dict]:
    """Experience entries or projects as {title, org, dates, facts}, most recent first (the profile's own order)."""
    if kind == "experience":
        return [
            {
                "kind": "experience",
                "title": e["role"],
                "org": e["company"].split("|")[0].strip(),
                "dates": e.get("dates", ""),
                "facts": [plain(b["html"]) for b in e.get("bullets", [])],
            }
            for e in profile["experience"]
        ]
    return [
        {
            "kind": "project",
            "title": p["name"],
            "org": "",
            "dates": p.get("date", ""),
            "facts": [plain(p.get("desc", ""))] + [plain(b["html"]) for b in p.get("bullets", [])],
            "github_url": p.get("github_url") or "",
        }
        for p in profile["projects"]
        if not _is_excluded(p)
    ]


def profile_context(profile: dict) -> str:
    """Short background block for the prompt: title, summary, education and roles (no bullets, those come with the featured item)."""
    lines = [f"Title: {profile['title']}", f"Summary: {plain(profile['summary'])}"]
    for ed in profile.get("education", []):
        lines.append(f"Education: {ed['degree']}, {ed['institution']} ({ed.get('date', '')})")
    for e in profile["experience"]:
        lines.append(f"Role: {e['role']}, {e['company'].split('|')[0].strip()} ({e.get('dates', '')})")
    return "\n".join(lines)


def format_item(item: dict) -> str:
    head = item["title"] + (f" at {item['org']}" if item["org"] else "") + (f" ({item['dates']})" if item["dates"] else "")
    return head + "\n" + "\n".join(f"- {f}" for f in item["facts"] if f)
