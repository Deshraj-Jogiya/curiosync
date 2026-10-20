"""Post drafting: three posts a week about the owner's own work, every fact taken from the live profile (see profile_source).

Flow for one post: pick the subject (post_plan.pick_subject) and an opening style (post_plan.pick_hook), write several drafts, run every
draft through post_rules.check_draft, keep the best one that passes, and if none passes ask for a corrected version at most twice. If it
still fails, DraftRejected is raised and nothing is posted that day.
"""

import asyncio
from datetime import date

from app.config import Settings
from app.services.compliance_service import humanize_draft
from app.services.llm_service import call_llm_with_fallback
from app.services.post_plan import HOOK_TYPES, matching_news, news_allowed, pick_hook, pick_subject
from app.services.post_rules import MAX_CHARS, MIN_CHARS, check_draft, tidy_hashtags
from app.services.profile_source import format_item, load_profile, profile_context
from app.utils.logging import logger

# Weekday -> format. News is not a fixed slot: on Friday a news post is written only when a news item names a tool the chosen subject
# actually used and no news post went out in the last few posts; otherwise Friday is a design-decision post.
POST_SCHEDULE = {0: "project_spotlight", 2: "lesson", 4: "decision"}

DRAFTS_PER_RUN = 3
MAX_REWRITES = 3


class DraftRejected(RuntimeError):
    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


COMMON_RULES = """You are Deshraj Jogiya, a {title}. Write one LinkedIn post in the first person about your own work. A recruiter or hiring
manager reading it should come away knowing exactly what you built, the decisions you made, and what it achieved.

Hard rules:
- Use only the facts in FEATURED, CONTEXT, YOUR OWN NOTES and BACKGROUND{news_clause}. Never invent numbers, tools, people, dates,
  incidents, team members, users, clients or feelings. If something is not given, leave it out.
- FEATURED is {solo_rule}
- {sim_rule}
- Motivation, struggles, "before" situations and feelings may only come from YOUR OWN NOTES. If YOUR OWN NOTES is empty, describe the
  decisions and results without any backstory.
- Never call yourself senior, lead or principal. Do not list your years of experience, other jobs or other results: stay on FEATURED.
- Plain text only: no markdown, no bold or italic unicode letters, no emoji, no all-capital headers, no bullet symbols other than a
  hyphen if a short list is really needed.
- No links, URLs, domain names or repository paths. Never say the post was generated, automated or scheduled.
- Do not ask readers to like, share, follow or comment. Do not end with a one-word question.
- Avoid these words: delve, leverage, crucial, seamless, robust, rigorous, significant, cutting-edge, pivotal, paramount, vital,
  critical, landscape, journey, unlock, elevate, game-changer, testament, realm, showcasing. Avoid "not just X but Y" and "it's not X,
  it's Y" constructions.

Focus:
- Choose at most three facts from FEATURED that serve the TASK and build the whole post around them. Do not mention the other facts;
  a post that lists everything reads like a resume.
- Never link two facts by cause and effect ("this came from", "which led to") unless one fact states that link itself.

Shape:
- First line: {hook} Keep it under 120 characters and make it a complete statement on its own, because only the first line shows
  before "see more".
- Then short paragraphs of one to three sentences separated by blank lines: the context, the decision and its trade-off, the result,
  and what you learned or would do the same way again.
- {ending}
- Total length {min_chars} to {max_chars} characters including spaces, then one last line with 2 or 3 relevant hashtags.
- Return only the post text.

BACKGROUND:
{background}

FEATURED:
{featured}

CONTEXT:
{context}

YOUR OWN NOTES:
{notes}
"""

FORMAT_TASKS = {
    "project_spotlight": "Write a breakdown of FEATURED: what it does, two or three specific design decisions and why, and the measurable result.",
    "lesson": "Write one practical engineering lesson drawn from FEATURED, explained through its concrete facts, with one thing a reader "
              "could apply in their own work.",
    "decision": "Write about ONE design decision in FEATURED: the options, why you chose the one you did, what it cost, and how it "
                "turned out according to the facts.",
    "news_take": "NEWS below names a tool you used in FEATURED. Open with the news itself and its source, then give your own view of what "
                 "it changes for people who build with that tool, tied to one specific thing you did in FEATURED.",
}

ENDINGS = {
    "project_spotlight": "End with one plain sentence saying you are open to {roles} roles.",
    "lesson": "End with one specific technical question to readers about how they handle the same problem.",
    "decision": "End with one plain sentence saying you are open to {roles} roles.",
    "news_take": "End with one specific technical question to readers.",
}


def post_format_for(day: date) -> str | None:
    return POST_SCHEDULE.get(day.weekday())


def roles_from_title(title: str) -> str:
    parts = [p.strip() for p in title.replace(" and ", " & ").split("&") if p.strip()]
    return " and ".join(parts) if parts else title


def source_text(profile: dict, item: dict, news: dict | None = None) -> str:
    """Every fact a post may use; post_rules checks numbers and tools against this."""
    parts = [profile_context(profile), format_item(item), item.get("context", ""), "\n".join(item.get("notes", []))]
    if news:
        parts.append(f"{news.get('source_name', '')} {news.get('title', '')} {news.get('summary', '')}")
    return "\n".join(p for p in parts if p)


def build_prompt(fmt: str, profile: dict, item: dict, hook_type: str, news: dict | None = None) -> str:
    roles = roles_from_title(profile["title"])
    if item["kind"] == "project" and item.get("solo", True):
        solo_rule = "a project you built alone: always write 'I', never 'we', 'our' or 'us'."
    else:
        solo_rule = "work you did as part of a company; describe your own part with 'I'."
    if item.get("simulated"):
        sim_rule = ("FEATURED used simulated or synthetic data. Say so plainly in the post (for example 'on simulated data'), and present "
                    "its numbers as results of the project, never as real business impact.")
    else:
        sim_rule = "Present results exactly as the facts state them, without inflating their scope."
    hook = HOOK_TYPES[hook_type]["instruction"] if fmt != "news_take" else "Open with the news itself and its source."
    prompt = COMMON_RULES.format(
        title=profile["title"],
        news_clause=" and NEWS" if news else "",
        solo_rule=solo_rule,
        sim_rule=sim_rule,
        hook=hook,
        ending=ENDINGS[fmt].format(roles=roles),
        min_chars=MIN_CHARS + 100,
        max_chars=MAX_CHARS - 150,
        background=profile_context(profile),
        featured=format_item(item),
        context=item.get("context") or "(none)",
        notes="\n".join(f"- {n}" for n in item.get("notes", [])) or "(empty)",
    )
    prompt += "\nTASK:\n" + FORMAT_TASKS[fmt] + "\n"
    if news:
        prompt += f"\nNEWS:\n[{news.get('source_name', '')}] {news.get('title', '')}\n{news.get('summary', '')[:400]}\n"
    return prompt


CRITIC_PROMPT = """You are checking a LinkedIn post against the only facts its author is allowed to use.

FACTS:
{facts}

POST:
{post}

List every factual statement about the author's work in POST that FACTS do not support. Count as unsupported: a feature or
capability not in FACTS, a number attached to a different thing than in FACTS, a cause-and-effect link between two facts that FACTS do
not state, a motivation, struggle or feeling not in FACTS, and a claim about users, clients or scale not in FACTS.
Do NOT count: rewording of a fact, the author's opinion or lesson clearly phrased as an opinion ("I would make the same choice again",
"what I take from this"), general engineering advice to readers, a correct general explanation of how a named tool or technique works (for example "a Snowflake
Python UDF runs the model inside the warehouse"), a closing question, or a sentence saying the author is open to roles.
Return only JSON: {{"unsupported": ["short description of each problem"]}}"""


async def critic_problems(text: str, facts: str, settings: Settings) -> list[str]:
    """Second-pass fact check by the model. Mechanical checks catch invented numbers and tools; this catches invented capabilities and
    misattributed results ("automated application submission", "this 60% came from the migration")."""
    import json
    import re

    try:
        raw = await call_llm_with_fallback(messages=[{"role": "user", "content": CRITIC_PROMPT.format(facts=facts, post=text)}],
                                           settings=settings, temperature=0.0)
    except Exception as exc:
        # An unchecked draft is never published: if the fact check cannot run, the draft fails it.
        return [f"fact check could not run ({type(exc).__name__})"]
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    try:
        found = json.loads(raw).get("unsupported", [])
    except ValueError:
        return ["fact check returned no readable answer"]
    return [f"unsupported by the facts: {p}" for p in found if isinstance(p, str) and p.strip()]


def _finish(text: str) -> str:
    return tidy_hashtags(humanize_draft(text))


def _rank(text: str) -> float:
    return abs(len(text) - (MIN_CHARS + MAX_CHARS) / 2)


async def _one_draft(prompt: str, settings: Settings) -> str:
    return _finish(await call_llm_with_fallback(messages=[{"role": "user", "content": prompt}], settings=settings, temperature=1.0))


async def generate_post(fmt: str, profile: dict, settings: Settings, day: date, news_items: list[dict] | None = None,
                        history: list[dict] | None = None) -> dict:
    """Write the day's post. Returns {text, subject, format, hook_type, item, attempts}; raises DraftRejected if nothing passes."""
    history = history or []
    item = pick_subject(profile, fmt, history, day)
    news = None
    if fmt == "decision" and news_items and news_allowed(history):
        news = matching_news(item, news_items)
        if news:
            fmt = "news_take"
    if fmt == "decision" and not item.get("notes"):
        # Why a decision was made can only come from the owner; without his notes a decision post would have to invent the reasons.
        fmt = "lesson"
    hook_type = pick_hook(item, history)
    prompt = build_prompt(fmt, profile, item, hook_type, news)
    facts = source_text(profile, item, news)
    logger.info("Drafting %s about %s (hook: %s)", fmt, item["title"], hook_type)

    results = await asyncio.gather(*(_one_draft(prompt, settings) for _ in range(DRAFTS_PER_RUN)), return_exceptions=True)
    drafts = [r for r in results if isinstance(r, str) and r.strip()]
    if not drafts:
        raise DraftRejected([f"no draft returned: {results[0]}"])
    checked = sorted(((d, check_draft(d, item, facts, history)) for d in drafts), key=lambda p: (len(p[1]), _rank(p[0])))
    best, problems = checked[0]
    attempts = len(drafts)
    if not problems:
        problems = await critic_problems(best, facts, settings)
        attempts += 1

    for _ in range(MAX_REWRITES):
        if not problems:
            break
        fix = (prompt + "\n\nYour previous draft is below. Rewrite it so it fixes every problem listed, keeping everything else that is "
               "true to the facts.\n\nPROBLEMS:\n" + "\n".join(f"- {p}" for p in problems) + "\n\nPREVIOUS DRAFT:\n" + best)
        best = _finish(await call_llm_with_fallback(messages=[{"role": "user", "content": fix}], settings=settings, temperature=0.7))
        problems = check_draft(best, item, facts, history)
        attempts += 1
        if not problems:
            problems = await critic_problems(best, facts, settings)
            attempts += 1

    if problems:
        raise DraftRejected(problems)
    logger.info("Draft accepted", extra={"format": fmt, "chars": len(best), "attempts": attempts})
    return {"text": best, "subject": item["title"], "format": fmt, "hook_type": hook_type, "item": item, "attempts": attempts,
            "news": news}


async def generate_draft(news_items: list[dict], settings: Settings) -> str:
    """Draft for the web app's Generate button: today's scheduled format, or a project post on days without one."""
    profile = await load_profile()
    fmt = post_format_for(date.today()) or "project_spotlight"
    result = await generate_post(fmt, profile, settings, date.today(), news_items)
    return result["text"]


def validate_draft_length(text: str) -> tuple[bool, int]:
    """Check whether the draft falls within the character window the posts are written to."""
    n = len(text)
    return MIN_CHARS <= n <= MAX_CHARS, n
