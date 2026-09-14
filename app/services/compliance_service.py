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

    # Convert markdown links [label](url) to plain text "label - url" to prevent LinkedIn parser from truncating the post
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 - \2", text)

    # Convert any other remaining brackets and parentheses to spaces to avoid triggering LinkedIn's parser
    text = text.replace("[", " ").replace("]", " ").replace("(", " ").replace(")", " ")

    # Remove any other stray unicode replacement characters
    text = text.replace("\ufffd", "")

    return text


def humanize_draft(text: str) -> str:
    """Remove or replace robotic phrases and clean special characters."""
    original = text
    text = clean_special_characters(text)
    text = fix_experience_claims(text)

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


# The real, verified figure across every synced profile source (CRM, portfolio,
# LinkedIn, resume). If a draft claims a different tenure, it's an LLM fabrication,
# not a fact — this is exactly how "five years" (vs the real "3+ years") slipped
# into published posts undetected for months: nothing ever checked the generated
# text against the real number.
REAL_YEARS_EXPERIENCE = 3

_NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}

_EXPERIENCE_CLAIM_PATTERN = re.compile(
    r"\b(\d+|" + "|".join(_NUMBER_WORDS) + r")\+?\s*years?\s+"
    r"(?:of\s+)?(?:systems\s+|professional\s+)?(?:engineering\s+)?experience\b",
    re.IGNORECASE,
)


def check_experience_claims(text: str) -> list[str]:
    """Flag any 'N years of experience' claim that doesn't match the real figure."""
    issues: list[str] = []
    for match in _EXPERIENCE_CLAIM_PATTERN.finditer(text):
        raw = match.group(1).lower()
        claimed = _NUMBER_WORDS.get(raw, None)
        if claimed is None:
            try:
                claimed = int(raw)
            except ValueError:
                continue
        if claimed != REAL_YEARS_EXPERIENCE:
            issues.append(
                f"Claims '{match.group(0)}' — real figure is "
                f"{REAL_YEARS_EXPERIENCE}+ years, not {claimed}"
            )
    return issues


def fix_experience_claims(text: str) -> str:
    """Mechanically correct any wrong 'N years of experience' claim in place.

    check_experience_claims only detects the problem; this actually fixes it so a
    bad claim never reaches LinkedIn, regardless of what the LLM generated. Runs
    unconditionally (not just when a mismatch is found) since it's a cheap no-op
    on already-correct text.
    """

    def _replace(match: re.Match) -> str:
        raw = match.group(1).lower()
        claimed = _NUMBER_WORDS.get(raw, None)
        if claimed is None:
            try:
                claimed = int(raw)
            except ValueError:
                return match.group(0)
        if claimed == REAL_YEARS_EXPERIENCE:
            return match.group(0)
        logger.warning(
            "Correcting fabricated experience claim in draft: '%s' -> '%s+ years of experience'",
            match.group(0),
            REAL_YEARS_EXPERIENCE,
        )
        return f"{REAL_YEARS_EXPERIENCE}+ years of experience"

    return _EXPERIENCE_CLAIM_PATTERN.sub(_replace, text)


def check_compliance(text: str, sources: list[dict]) -> dict:
    """Validate a draft against LinkedIn and content-quality rules.

    Returns {"passed": bool, "issues": list[str]}.
    """
    issues: list[str] = []

    issues.extend(check_experience_claims(text))

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
