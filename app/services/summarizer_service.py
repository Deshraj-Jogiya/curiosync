"""Post drafting: three formats a week, every fact taken from the live profile (see profile_source)."""

from datetime import date

from app.config import Settings
from app.services.llm_service import call_llm_with_fallback
from app.services.profile_source import featurable_items, format_item, load_profile, profile_context
from app.utils.logging import logger

# Weekday -> format. Three strong posts a week instead of seven templated ones; other days draft nothing (the TIL note still runs daily).
POST_SCHEDULE = {0: "project_spotlight", 2: "news_take", 4: "lesson"}

COMMON_RULES = """You are Deshraj Jogiya, a {title}, writing one LinkedIn post in the first person.

Rules:
- Plain text only: no markdown, no bold or italic unicode letters, no all-capital section headers, no emojis.
- Open with a single hook line of under 15 words, specific to FEATURED, that states a concrete number, decision or opinion. Never open with
  a generic statement about an industry, "In today's", or a question about "the world of".
- Short paragraphs of one to three sentences, separated by blank lines.
- Use only the facts in FEATURED and BACKGROUND{news_clause}. Do not invent numbers, tools, team sizes, incidents, failures, people or dates. If a fact is not given, leave it out.
- BACKGROUND is context, not material: do not add a paragraph listing your years of experience, other jobs or other results. Stay on FEATURED.
- Never call yourself senior, lead or principal.
- Avoid filler words: game-changer, crucial, seamless, seamlessly, robust, rigorous, leverage, significant, cutting-edge, delve.
- No links, URLs, domain names, repository names written as paths, or "link in comments".
- Never say the post was generated, automated, scheduled or compiled by a tool.
- {length} words, then 2 or 3 relevant hashtags on the last line.
- Return only the post text.

BACKGROUND:
{background}

FEATURED:
{featured}
"""

FORMAT_TASKS = {
    "project_spotlight": (
        "170 to 260",
        "Write a project breakdown of FEATURED: the problem it solves, two or three specific design decisions and why they were made, and "
        "the measurable result. Close with one plain sentence saying you are open to {roles} roles.",
    ),
    "news_take": (
        "150 to 230",
        "Pick the ONE item from NEWS that matters most to people who build data pipelines or machine learning systems. Name its source, then "
        "give your own view in two or three short paragraphs: what it changes in practice and what to watch out for. Connect it to one specific "
        "thing from FEATURED that you actually did, in one paragraph. Close with a genuine question to readers.",
    ),
    "lesson": (
        "150 to 230",
        "Write one practical engineering lesson drawn from FEATURED. State the lesson in the hook, explain it with the concrete facts given, "
        "and give readers one thing they can apply this week. Close with one plain sentence saying you are open to {roles} roles.",
    ),
}


def post_format_for(day: date) -> str | None:
    return POST_SCHEDULE.get(day.weekday())


def pick_item(profile: dict, fmt: str, day: date) -> dict:
    """Rotate through subjects week by week so consecutive weeks feature different work."""
    year, week, _ = day.isocalendar()
    n = year * 53 + week
    if fmt == "project_spotlight":
        pool = featurable_items(profile, "project")
    elif fmt == "news_take":
        pool = featurable_items(profile, "experience")
    else:
        exp, proj = featurable_items(profile, "experience"), featurable_items(profile, "project")
        pool = [x for pair in zip(exp, proj) for x in pair] + exp[len(proj):] + proj[len(exp):]
    return pool[n % len(pool)]


def roles_from_title(title: str) -> str:
    parts = [p.strip() for p in title.replace(" and ", " & ").split("&") if p.strip()]
    return " and ".join(parts) if parts else title


def build_prompt(fmt: str, profile: dict, item: dict, news_items: list[dict] | None = None) -> str:
    length, task = FORMAT_TASKS[fmt]
    prompt = COMMON_RULES.format(
        title=profile["title"],
        news_clause=" and NEWS" if fmt == "news_take" else "",
        length=length,
        background=profile_context(profile),
        featured=format_item(item),
    )
    prompt += "\nTASK:\n" + task.format(roles=roles_from_title(profile["title"])) + "\n"
    if fmt == "news_take":
        prompt += "\nNEWS:\n" + _format_news_for_prompt(news_items or []) + "\n"
    return prompt


async def generate_post(fmt: str, profile: dict, settings: Settings, day: date, news_items: list[dict] | None = None) -> tuple[str, str]:
    """Return (post text, featured subject title)."""
    item = pick_item(profile, fmt, day)
    prompt = build_prompt(fmt, profile, item, news_items)
    logger.info("Generating %s post about %s", fmt, item["title"])
    text = await call_llm_with_fallback(messages=[{"role": "user", "content": prompt}], settings=settings, temperature=0.7)
    logger.info("Draft generated", extra={"format": fmt, "word_count": len(text.split()), "char_count": len(text)})
    return text, item["title"]


def _format_news_for_prompt(news_items: list[dict]) -> str:
    """Format news items into a numbered list for the prompt."""
    lines: list[str] = []
    for i, item in enumerate(news_items, 1):
        summary = item.get("summary", "")
        source = item.get("source_name", "")
        lines.append(f"{i}. [{source}] {item['title']}")
        if summary:
            lines.append(f"   {summary[:200]}")
    return "\n".join(lines)


async def generate_draft(news_items: list[dict], settings: Settings) -> str:
    """News-take draft for today, used by the web app's Generate button."""
    profile = await load_profile()
    text, _ = await generate_post("news_take", profile, settings, date.today(), news_items)
    return text


def validate_draft_length(text: str) -> tuple[bool, int]:
    """Check whether the draft falls within the 150–300 word target range."""
    word_count = len(text.split())
    valid = 150 <= word_count <= 300
    return valid, word_count
