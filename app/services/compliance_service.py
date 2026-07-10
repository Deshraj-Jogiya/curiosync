"""Compliance checking and humanization service."""

import re

from app.utils.logging import logger

ROBOTIC_PHRASES: list[str] = [
    "In conclusion",
    "It's worth noting",
    "Let's dive in",
    "Without further ado",
    "In today's fast-paced",
    "It goes without saying",
    "Needless to say",
    "At the end of the day",
    "Moving forward",
    "game-changer",
    "disruptive",
    "synergy",
    "leverage",
    "paradigm shift",
    "deep dive",
]

# Mapping of robotic phrases to natural replacements (or empty to just remove)
_REPLACEMENTS: dict[str, str] = {
    "In conclusion": "To sum up",
    "It's worth noting": "Notably",
    "Let's dive in": "",
    "Without further ado": "",
    "In today's fast-paced": "In today's",
    "It goes without saying": "",
    "Needless to say": "",
    "At the end of the day": "Ultimately",
    "Moving forward": "Going ahead",
    "game-changer": "significant development",
    "disruptive": "transformative",
    "synergy": "collaboration",
    "leverage": "use",
    "paradigm shift": "major shift",
    "deep dive": "close look",
}


def clean_special_characters(text: str) -> str:
    """Normalize curly quotes, dashes, and fix unicode replacement character bugs."""
    # Remove null bytes and other ASCII control characters (except \n, \r, \t)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    # Normalize common curly punctuation to straight ascii
    replacements = {
        "’": "'",
        "‘": "'",
        "“": '"',
        "”": '"',
        "–": "-",  # en dash
        "—": "-",  # em dash
    }
    for search, replace in replacements.items():
        text = text.replace(search, replace)

    # Fix instances where apostrophes got converted to unicode replacement character ( / \ufffd)
    # e.g., "OpenAIs" -> "OpenAI's"
    text = re.sub(r"(\w)[\ufffd\u2019\u2018\u201b\u0092](\w)", r"\1'\2", text)

    # Remove any other stray unicode replacement characters
    text = text.replace("\ufffd", "")

    return text


def humanize_draft(text: str) -> str:
    """Remove or replace robotic phrases and clean special characters."""
    original = text
    text = clean_special_characters(text)

    for phrase in ROBOTIC_PHRASES:
        pattern = re.compile(re.escape(phrase), re.IGNORECASE)
        replacement = _REPLACEMENTS.get(phrase, "")
        text = pattern.sub(replacement, text)

    # Clean up double spaces and leading/trailing whitespace on lines
    text = re.sub(r"  +", " ", text)
    text = "\n".join(line.strip() for line in text.splitlines())
    text = re.sub(r"\n{3,}", "\n\n", text)

    if text != original:
        logger.info("Humanized draft — cleaned robotic phrases and characters")

    return text.strip()


def check_compliance(text: str, sources: list[dict]) -> dict:
    """Validate a draft against LinkedIn and content-quality rules.

    Returns {"passed": bool, "issues": list[str]}.
    """
    issues: list[str] = []

    # Word count check (150-320)
    word_count = len(text.split())
    if word_count < 150:
        issues.append(f"Too short: {word_count} words (minimum 150)")
    elif word_count > 320:
        issues.append(f"Too long: {word_count} words (maximum 320)")

    # Character limit (LinkedIn max ~3000)
    if len(text) > 3000:
        issues.append(f"Exceeds LinkedIn character limit: {len(text)} chars (max 3000)")

    # No credential collection language
    credential_patterns = [
        r"enter your password",
        r"send me your login",
        r"share your credentials",
        r"click here to verify your account",
        r"provide your (username|password|SSN|credit card)",
    ]
    for pattern in credential_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            issues.append(f"Contains credential collection language: '{pattern}'")

    # No scraping references
    scraping_patterns = [
        r"web\s*scrap(e|ing)",
        r"data\s*scrap(e|ing)",
        r"scraping\s*(tool|bot|script)",
    ]
    for pattern in scraping_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            issues.append("References web scraping — may violate LinkedIn ToS")

    passed = len(issues) == 0
    logger.info(
        "Compliance check complete",
        extra={"passed": passed, "issue_count": len(issues), "word_count": word_count},
    )
    return {"passed": passed, "issues": issues}
