"""Mechanical checks every draft must pass before it can be published.

Posts go out without a per-post human review, so these checks are the safety net: a draft that fails any of them is rewritten (bounded)
and, if it still fails, nothing is posted that day. A skipped day is always better than a post with an invented number, a tool the
project never used, "we" on solo work, or a simulation presented as a real business result.
"""

import re

# Length window: the research found engagement best around 1,200-1,800 characters (AuthoredUp 2025-26; Ordinal's data disagrees), but a
# post limited to two or three real facts runs shorter, and padding is worse than brevity. The "see more" fold on mobile is about 140
# characters, so the first line has to carry the claim on its own.
MIN_CHARS = 800
MAX_CHARS = 1700
MAX_FIRST_LINE = 140
MAX_HASHTAGS = 2  # 0-2 topic labels: more adds nothing and 10+ hurts (LinkedIn research, Oct 2026)

# Technologies that, if named in a draft, must appear in the featured item's facts or the background. Matching is case-insensitive on
# whole words. The list only needs to cover tools the model is likely to drop in uninvited.
TECH_TERMS = [
    "python", "sql", "pyspark", "spark", "scala", "java", "c#", ".net", "asp.net", "typescript", "javascript", "node.js", "react",
    "react native", "angular", "php", "codeigniter", "htmx", "fastapi", "flask", "django", "spring boot", "spring webflux", "r2dbc",
    "snowflake", "databricks", "dbt", "airflow", "dagster", "kafka", "flink", "delta lake", "iceberg", "parquet", "hadoop", "hive",
    "aws", "glue", "s3", "lambda", "redshift", "emr", "kinesis", "azure", "adls", "synapse", "gcp", "bigquery", "terraform", "docker",
    "kubernetes", "jenkins", "github actions", "postgresql", "postgres", "mysql", "mongodb", "sqlite", "redis", "supabase",
    "elasticsearch", "great expectations", "mlflow", "tableau", "power bi", "looker", "arcgis", "streamlit", "pandas", "numpy",
    "scikit-learn", "tensorflow", "pytorch", "keras", "xgboost", "jax", "langchain", "llamaindex", "semantic kernel", "spacy", "bert",
    "gpt-4o", "openai", "gemini", "claude", "llama", "lora", "hugging face", "pgvector", "onnx", "opencv", "oracle cloud", "selenium",
    "playwright", "graphql",
]

BANNED_WORDS = [
    "delve", "delving", "leverage", "leveraged", "leveraging", "game-changer", "game changer", "crucial", "seamless", "seamlessly",
    "robust", "rigorous", "significant", "significantly", "cutting-edge", "pivotal", "paramount", "vital", "critical", "tapestry",
    "testament", "realm", "intricate", "showcasing", "spearheaded", "synergy", "unlock", "unleash", "elevate", "empower",
    "revolutionize", "transformative", "landscape", "navigate", "journey", "embark", "deep dive", "dive into", "in today's",
    "ever-evolving", "fast-paced", "at the end of the day", "humbled", "thrilled", "excited to share", "proud to announce",
    "game changing", "next level", "harness",
]

# Structural AI tells (Wikipedia "Signs of AI writing"; Washington Post analysis via Decrypt): negative parallelism and stock closers.
STRUCTURE_PATTERNS = [
    (r"\bnot (?:just|only|merely) [^.!?\n]{1,60}\bbut\b", "'not just X but Y' construction"),
    (r"\bit'?s not [^.!?\n]{1,40}[,;] it'?s\b", "'it's not X, it's Y' construction"),
    (r"\bhere'?s the thing\b", "'here's the thing'"),
    (r"\bthe (?:best|good) part\?", "rhetorical 'the best part?'"),
    (r"\blet that sink in\b", "'let that sink in'"),
    (r"\b(?:thoughts|agree)\?\s*$", "one-word engagement question"),
]

ENGAGEMENT_BAIT = re.compile(
    # "like this post" is bait; "scoring like this" is a comparison, so a bare "like this" is not flagged.
    r"\b(?:like|share|repost)\s+(?:this\s+(?:post|if)|if|for)\b|\bfollow\s+(?:me|for)\b|\bcomment\s+(?:below|yes|'|\")|\btag someone\b|\bdrop a\b",
    re.IGNORECASE,
)

# A story the facts do not contain: "our initial process was largely manual", "this created a bottleneck". Only allowed when the facts or
# the owner's own notes say so.
INVENTED_STORY_TERMS = ["bottleneck", "struggled", "frustrat", "pain point", "largely manual", "initially", "originally", "used to take",
                        "sleepless", "late nights", "headache", "nightmare"]

_EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️]")
_STYLED_UNICODE = re.compile("[\U0001D400-\U0001D7FF]")
_NUMBER = re.compile(r"(?<![\w.])\$?\d[\d,]*(?:\.\d+)?\s*(?:%|x\b|k\b|m\b|ms\b)?", re.IGNORECASE)
_SIMULATED = re.compile(r"simulat|synthetic", re.IGNORECASE)
_WE = re.compile(r"\b(?:we|our|us|ours)\b", re.IGNORECASE)


def _norm_number(raw: str) -> str:
    return re.sub(r"[\s,$]", "", raw.lower()).rstrip(".")


def numbers_in(text: str) -> set[str]:
    return {_norm_number(m.group(0)) for m in _NUMBER.finditer(text)}


def _bare(n: str) -> str:
    return re.sub(r"[^\d.]", "", n)


def unsupported_numbers(draft: str, source: str) -> list[str]:
    """Numbers in the draft that the source facts do not contain. Small counts (2-10) are allowed: "three decisions", "step 2"."""
    known = numbers_in(source)
    known_bare = {_bare(n) for n in known}
    bad = []
    for n in sorted(numbers_in(draft)):
        b = _bare(n)
        if not b:
            continue
        if n in known or (b in known_bare and not n.endswith("%")) or (n.endswith("%") and n in known):
            continue
        if b.isdigit() and int(b) <= 10 and not n.endswith(("%", "x")):
            continue
        bad.append(n)
    return bad


def _term_in(term: str, text: str) -> bool:
    return re.search(r"(?<![\w.])" + re.escape(term) + r"(?![\w])", text, re.IGNORECASE) is not None


def unsupported_tools(draft: str, source: str) -> list[str]:
    """Tools named in the draft that the source never mentions (e.g. a diagram or post adding Kafka to a project that never used it)."""
    found = []
    for term in TECH_TERMS:
        if _term_in(term, draft) and not _term_in(term, source):
            # "spark" is satisfied by "pyspark"/"spark sql", "postgres" by "postgresql", "react" by "react native"/"react js"
            if any(_term_in(t, source) for t in TECH_TERMS if term in t and t != term):
                continue
            if any(_term_in(t, draft) and term in t and t != term and _term_in(t, source) for t in TECH_TERMS):
                continue
            found.append(term)
    return found


def first_words(text: str, n: int = 10) -> list[str]:
    first = text.strip().splitlines()[0] if text.strip() else ""
    return re.findall(r"[a-z0-9%']+", first.lower())[:n]


def _shingles(words: list[str], k: int) -> set[tuple]:
    return {tuple(words[i:i + k]) for i in range(len(words) - k + 1)}


def body_similarity(a: str, b: str) -> float:
    """Jaccard similarity of 5-word shingles; near-duplicate bodies score high, different posts on the same project stay low."""
    wa, wb = re.findall(r"[a-z0-9%']+", a.lower()), re.findall(r"[a-z0-9%']+", b.lower())
    sa, sb = _shingles(wa, 5), _shingles(wb, 5)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def tidy_hashtags(text: str) -> str:
    """Collect hashtags onto one final line, at most MAX_HASHTAGS, and drop hashtag-only lines elsewhere."""
    tags: list[str] = []
    kept: list[str] = []
    for line in text.strip().splitlines():
        words = line.split()
        if words and all(w.startswith("#") for w in words):
            tags.extend(w for w in words if w not in tags)
        else:
            kept.append(line)
    body = "\n".join(kept).rstrip()
    tags = tags[:MAX_HASHTAGS]
    return body + ("\n\n" + " ".join(tags) if tags else "")


def check_draft(draft: str, item: dict, source_text: str, history: list[dict]) -> list[str]:
    """Return every rule the draft breaks; an empty list means it may be published.

    item: the featured subject (kind, solo, simulated, notes). source_text: every fact the post may use (featured facts, background, the
    owner's own notes, and for news posts the news headline). history: previously published posts, newest last.
    """
    problems: list[str] = []
    text = draft.strip()
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return ["empty draft"]

    if len(text) < MIN_CHARS or len(text) > MAX_CHARS:
        problems.append(f"length {len(text)} characters, must be {MIN_CHARS}-{MAX_CHARS}")
    if len(lines[0]) > MAX_FIRST_LINE:
        problems.append(f"first line is {len(lines[0])} characters, must be at most {MAX_FIRST_LINE} so it shows before 'see more'")

    for n in unsupported_numbers(text, source_text):
        problems.append(f"number '{n}' is not in the facts")
    for t in unsupported_tools(text, source_text):
        problems.append(f"names '{t}', which the facts never mention")

    if item.get("kind") == "project" and item.get("solo", True) and _WE.search(text):
        problems.append("uses we/our/us on a solo project; write 'I'")
    if item.get("simulated") and not _SIMULATED.search(text):
        problems.append("the project used simulated or synthetic data; the post must say so")

    lower = text.lower()
    for w in BANNED_WORDS:
        if re.search(r"(?<![\w-])" + re.escape(w) + r"(?![\w-])", lower):
            problems.append(f"filler word '{w}'")
    for pattern, label in STRUCTURE_PATTERNS:
        if re.search(pattern, lower, re.MULTILINE):
            problems.append(f"AI-tell: {label}")
    if ENGAGEMENT_BAIT.search(text):
        problems.append("asks for likes, shares, follows or comments (engagement bait)")
    src_lower = source_text.lower()
    for term in INVENTED_STORY_TERMS:
        if term in lower and term not in src_lower:
            problems.append(f"'{term}' describes a backstory the facts do not contain")

    if _EMOJI.search(text):
        problems.append("contains emoji")
    if _STYLED_UNICODE.search(text):
        problems.append("contains unicode bold/italic letters")
    if len(re.findall(r"(?<!\w)#\w+", text)) > MAX_HASHTAGS:
        problems.append(f"more than {MAX_HASHTAGS} hashtags")
    if text.count("—") > 1:
        problems.append("more than one em dash")

    opener = first_words(text)
    for past in history[-30:]:
        past_open = past.get("opener_words") or first_words(past.get("text", ""))
        if _shingles(opener, 3) & _shingles(past_open, 3):
            problems.append(f"opening line repeats wording from the {past.get('date', 'earlier')} post")
            break
    for past in history[-12:]:
        sim = body_similarity(text, past.get("text", ""))
        if sim > 0.25:
            problems.append(f"too similar ({sim:.2f}) to the {past.get('date', 'earlier')} post")
            break

    return problems
