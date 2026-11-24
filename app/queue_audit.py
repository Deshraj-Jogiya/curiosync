"""Checks every approved post still waiting to go out, so a broken one fails the run (and GitHub emails the owner) days before its
post day instead of being found on LinkedIn. Run: python -m app.queue_audit"""

import os
import sys

from app.services.approved_queue import unposted
from app.services.post_document import overflows
from app.services.post_plan import load_history


def problems(history: list[dict] | None = None, queue_path: str | None = None) -> list[str]:
    history = load_history() if history is None else history
    posted_stories = {h.get("story_id") for h in history if h.get("story_id")}
    out, days, borrowed = [], {}, {}
    for e in unposted(history, queue_path):
        name = f"{e.get('post_day')} {e['id']}"
        if not (e.get("text") or "").strip():
            out.append(f"{name}: no post text")
        img = e.get("image")
        if not img or not os.path.exists(img):
            out.append(f"{name}: image missing ({img})")
        elif overflows(img):
            out.append(f"{name}: text runs past the image's edge")
        doc = e.get("document")
        if doc not in (None, "", "None") and (not os.path.exists(doc) or os.path.getsize(doc) == 0):
            out.append(f"{name}: document missing ({doc})")
        day = e.get("post_day")
        if day in days:
            out.append(f"{name}: same post day as {days[day]}")
        days[day] = e["id"]
        sid = (e.get("history_entry") or {}).get("story_id")
        if sid and sid in posted_stories:
            out.append(f"{name}: its story {sid} was already posted")
        for b in e.get("document_story_ids") or []:
            if b in borrowed:
                out.append(f"{name}: borrows {b}, which {borrowed[b]} also shows")
            borrowed[b] = e["id"]
    return out


if __name__ == "__main__":
    found = problems()
    for p in found:
        print(f"QUEUE PROBLEM: {p}")
    print(f"{len(found)} problem(s) in the approved queue")
    sys.exit(1 if found else 0)
