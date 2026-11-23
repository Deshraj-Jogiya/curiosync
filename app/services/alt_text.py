"""The image description LinkedIn reads with the post.

LinkedIn's 2026 feed matches a post's text to members' profiles with a language model, and an image carries its meaning only through
its alt text. The drafted alt texts were lists of numbers ("Bar chart ... Per series (ms): 5,350 19.6, ..."), so the image told that
model nothing about what was shown or which skills it used. At publish time the description now leads with the post's own first
line (its claim, already approved), then the chart description, then the demanded skills the story shows. Nothing is written that
is not already in the approved post or the story."""

import re

MAX_ALT = 4086  # LinkedIn's limit for image alt text


def _first_sentence(text: str) -> str:
    line = next((ln.strip() for ln in (text or "").splitlines() if ln.strip()), "")
    line = re.sub(r"\s*#\w+", "", line).strip()
    return line if line[-1:] in ".!?" else (line + "." if line else "")


def describe(alt: str | None, post_text: str, story: dict | None = None) -> str:
    alt = (alt or "").strip()
    parts = []
    claim = _first_sentence(post_text)
    if claim and claim.lower()[:40] not in alt.lower():
        parts.append(claim)
    if alt:
        parts.append(alt if alt[-1:] in ".!?" else alt + ".")
    if story:
        from app.services import market_skills

        skills = [s["term"] for s in market_skills.story_skills(story, market_skills.load())][:5]
        if skills and "Skills shown:" not in alt:
            parts.append("Skills shown: " + ", ".join(skills) + ".")
    return " ".join(parts)[:MAX_ALT]
