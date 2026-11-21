"""Warns the owner before the story bank runs dry. Each draft run counts the stories that could still be drafted (unposted, with
the owner's notes, and with chart data of their own); below RUNWAY_MIN an issue is opened on the CurioSync repository, which GitHub
emails to the owner, and it is closed again once the count recovers (owner, 2026-11-21: "in future I don't want to hit the
needle where this type of situation comes up")."""

import os

import httpx

from app.utils.logging import logger

RUNWAY_MIN = 6
TITLE = "Story bank running low"


def _body(count: int) -> str:
    return (f"Only {count} stories can still be drafted (minimum {RUNWAY_MIN}). A story needs your notes on why the project was "
            "built (data/subject_notes.json) and chart data of its own: a curve or series CSV, a comparison table, or steps of a "
            "process named as its source in the project's write-up. Adding notes for another project, or exporting the data "
            "behind an existing finding, refills it. This issue closes itself when the count is back to "
            f"{RUNWAY_MIN} or more.")


async def check(count: int, repo: str | None = None, token: str | None = None) -> str:
    repo = repo or os.getenv("GITHUB_REPOSITORY")
    token = token or os.getenv("GITHUB_TOKEN")
    if not repo or not token:
        return f"{count} drawable stories left (no GitHub token, no alarm)"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    api = f"https://api.github.com/repos/{repo}/issues"
    try:
        async with httpx.AsyncClient(timeout=20, headers=headers) as client:
            resp = await client.get(api, params={"state": "open", "per_page": 100})
            resp.raise_for_status()
            open_issue = next((i for i in resp.json() if i.get("title") == TITLE and "pull_request" not in i), None)
            if count < RUNWAY_MIN:
                if open_issue:
                    await client.patch(f"{api}/{open_issue['number']}", json={"body": _body(count)})
                    return f"{count} drawable stories left; alarm issue #{open_issue['number']} updated"
                made = await client.post(api, json={"title": TITLE, "body": _body(count)})
                made.raise_for_status()
                return f"{count} drawable stories left; alarm issue #{made.json()['number']} opened"
            if open_issue:
                await client.patch(f"{api}/{open_issue['number']}", json={"state": "closed"})
                return f"{count} drawable stories left; alarm issue #{open_issue['number']} closed"
    except httpx.HTTPError as exc:
        logger.warning("Story runway alarm failed: %s", exc)
        return f"{count} drawable stories left (alarm failed: {exc})"
    return f"{count} drawable stories left"
