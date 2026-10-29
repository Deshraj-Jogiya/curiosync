"""Neutral padding for test drafts that must reach the word minimum without tripping the repetition rule: every word is a distinct
made-up syllable pair, grouped into short sentences, so no word or number repeats."""

from itertools import product

_SYLLABLES = ["ba", "ke", "mi", "do", "lu", "fo", "zu", "po", "vi", "nu", "ga", "fe", "hy", "jo"]


def filler(words: int = 140) -> str:
    made = ["".join(p) for p in product(_SYLLABLES, repeat=2)][:words]
    return " ".join(" ".join(made[i:i + 8]).capitalize() + "." for i in range(0, len(made), 8))
