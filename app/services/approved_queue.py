"""Posts the owner has already approved word for word, used before any new draft is written.

data/approved_queue.json holds them in posting order. On a post day the first one not yet in the published-post history goes out as it
is: no model call, no rewrite, no profile fetch, so a Gemini outage or a quota limit cannot change or block it. A queued post counts as
published once a history entry carries its id (the publish job commits that entry), so an unapproved day just moves it to the next post day.
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
    posted_ids = {h.get("approved_id") for h in history}
    posted_texts = {h.get("text", "").strip() for h in history}
    for item in load_queue(path):
        if item["id"] not in posted_ids and item["text"].strip() not in posted_texts:
            return item
    return None


def image_copy(item: dict) -> str | None:
    """A temporary copy of the queued image, since the draft step deletes the image it hands to the publish job."""
    src = item.get("image")
    if not src or not os.path.exists(src):
        return None
    fd, dst = tempfile.mkstemp(suffix=os.path.splitext(src)[1] or ".png")
    os.close(fd)
    shutil.copy(src, dst)
    return dst
