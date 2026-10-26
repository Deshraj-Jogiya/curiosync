"""Posts the owner has approved, waiting for their post day.

data/approved_queue.json holds them in posting order: posts approved in chat, and drafts approved in GitHub (the approve job adds them).
On each Mon/Wed/Fri the first one not yet in the published-post history goes out word for word, with no model call, so a Gemini outage or
quota limit cannot change or block it. A queued post counts as published once a history entry carries its id.
"""

import json
import os
import shutil
import tempfile

QUEUE_PATH = os.path.join("data", "approved_queue.json")


def load_queue(path: str | None = None) -> list[dict]:
    try:
        with open(path or QUEUE_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return []


def next_approved(history: list[dict], path: str | None = None) -> dict | None:
    waiting = unposted(history, path)
    return waiting[0] if waiting else None


def image_copy(item: dict) -> str | None:
    """A temporary copy of the queued image, since the draft step deletes the image it hands to the publish job."""
    src = item.get("image")
    if not src or not os.path.exists(src):
        return None
    fd, dst = tempfile.mkstemp(suffix=os.path.splitext(src)[1] or ".png")
    os.close(fd)
    shutil.copy(src, dst)
    return dst


# Approved posts kept ready ahead of their post day (one week of Mon/Wed/Fri). Drafting pauses once this many are waiting.
QUEUE_AHEAD = 3


def unposted(history: list[dict], path: str | None = None) -> list[dict]:
    posted_ids = {h.get("approved_id") for h in history}
    posted_texts = {h.get("text", "").strip() for h in history}
    return [i for i in load_queue(path) if i["id"] not in posted_ids and i["text"].strip() not in posted_texts]


def add_to_queue(item: dict, path: str | None = None) -> None:
    queue = load_queue(path)
    queue.append(item)
    with open(path or QUEUE_PATH, "w", encoding="utf-8") as f:
        json.dump(queue, f, indent=2, ensure_ascii=False)


def open_post_days(today, history: list[dict], horizon: int = 28) -> list:
    """Post days from today on, leaving out today if something was already posted today."""
    from datetime import timedelta

    from app.services.summarizer_service import post_format_for

    posted_today = any(h.get("date") == str(today) for h in history)
    days = [today + timedelta(days=i) for i in range(horizon)]
    return [d for d in days if post_format_for(d) and not (d == today and posted_today)]


def slot_for_next_draft(today, history: list[dict], path: str | None = None):
    """The post day a new draft would fill: the first open post day after the ones already taken by approved posts."""
    return open_post_days(today, history)[len(unposted(history, path))]
