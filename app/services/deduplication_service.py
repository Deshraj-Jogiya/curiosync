"""News deduplication service using title similarity."""

import hashlib
import re
from difflib import SequenceMatcher

from app.utils.logging import logger

SIMILARITY_THRESHOLD = 0.75


def generate_dedup_hash(title: str) -> str:
    """Normalize a title and return its MD5 hash for exact-match deduplication."""
    normalized = title.lower()
    normalized = re.sub(r"[^\w\s]", "", normalized)
    words = sorted(normalized.split())
    return hashlib.md5(" ".join(words).encode()).hexdigest()


def deduplicate_news(items: list[dict]) -> list[dict]:
    """Remove near-duplicate news items, keeping the highest-credibility source per group."""
    if not items:
        return []

    kept: list[dict] = []

    for item in items:
        is_duplicate = False
        for i, existing in enumerate(kept):
            ratio = SequenceMatcher(None, item["title"].lower(), existing["title"].lower()).ratio()
            if ratio >= SIMILARITY_THRESHOLD:
                is_duplicate = True
                # Replace if the new item has higher credibility
                if item.get("relevance_score", 0) > existing.get("relevance_score", 0):
                    kept[i] = item
                break

        if not is_duplicate:
            kept.append(item)

    removed = len(items) - len(kept)
    if removed:
        logger.info("Deduplicated news items", extra={"original": len(items), "kept": len(kept), "removed": removed})

    return kept
