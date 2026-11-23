"""Tells the owner the moment a post goes live, so he can answer comments in its first hour (author replies come with about 30%
more engagement, Buffer 2025, 72k posts). GitHub's scheduler starts the daily run hours late (13:17 UTC runs started between 20:00
and 23:00 UTC in November 2026), so the posting time is not known in advance; a comment on one standing issue, which GitHub emails
to the owner, says when it happened."""

import os

import httpx

from app.utils.logging import logger

TITLE = "Post is live"


def post_url(post_id: str | None) -> str | None:
    return f"https://www.linkedin.com/feed/update/{post_id}/" if post_id else None


def _body(entry: dict) -> str:
    url = post_url(entry.get("post_id"))
    opener = (entry.get("text") or "").strip().splitlines()[0][:200] if entry.get("text") else entry.get("subject", "")
    owner = os.getenv("GITHUB_REPOSITORY_OWNER", "")
    mention = f"@{owner} " if owner else ""
    lines = [f"{mention}today's post is live ({entry.get('subject', '')}).", "", f"> {opener}", ""]
    if url:
        lines.append(f"Open it: {url}")
    lines += ["", "For the next hour: answer every comment with a real reply (a question back, a detail, a thank-you that adds "
              "something). Do not like or comment from other tools; LinkedIn limits reach for automated engagement."]
    return "\n".join(lines)


async def post_is_live(entry: dict, repo: str | None = None, token: str | None = None) -> str:
    repo = repo or os.getenv("GITHUB_REPOSITORY")
    token = token or os.getenv("GITHUB_TOKEN")
    if not repo or not token:
        return "no alert (no GitHub token)"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    api = f"https://api.github.com/repos/{repo}/issues"
    try:
        async with httpx.AsyncClient(timeout=20, headers=headers) as client:
            resp = await client.get(api, params={"state": "open", "per_page": 100})
            resp.raise_for_status()
            issue = next((i for i in resp.json() if i.get("title") == TITLE and "pull_request" not in i), None)
            if issue is None:
                made = await client.post(api, json={"title": TITLE, "body": "Each comment below marks a post going live."})
                made.raise_for_status()
                issue = made.json()
            sent = await client.post(f"{api}/{issue['number']}/comments", json={"body": _body(entry)})
            sent.raise_for_status()
            return f"alert on issue #{issue['number']}"
    except httpx.HTTPError as exc:
        logger.warning("Post-is-live alert failed: %s", exc)
        return f"alert failed ({exc})"
