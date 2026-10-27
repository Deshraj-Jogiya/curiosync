"""Post drafting: three posts a week about the owner's own work, every fact taken from the live profile (see profile_source).

Flow for one post: pick the subject (post_plan.pick_subject) and an opening style (post_plan.pick_hook), write several drafts, run every
draft through post_rules.check_draft, keep the best one that passes, and if none passes ask for a corrected version at most twice. If it
still fails, DraftRejected is raised and nothing is posted that day.
"""

import asyncio
import re
from datetime import date
from pathlib import Path

from app.config import Settings
from app.services.compliance_service import humanize_draft
from app.services.llm_service import call_llm_with_fallback
from app.services.post_plan import HOOK_TYPES, matching_news, news_allowed, pick_hook, pick_subject
from app.services.post_rules import (MAX_CHARS, MIN_CHARS, check_draft, drop_sentences_with_numbers, tidy_hashtags,
                                     unsupported_numbers)
from app.services.profile_source import format_item, load_profile, profile_context
from app.utils.logging import logger

# Weekday -> format. News is not a fixed slot: on Friday a news post is written only when a news item names a tool the chosen subject
# actually used and no news post went out in the last few posts; otherwise Friday is a design-decision post.
POST_SCHEDULE = {0: "project_spotlight", 2: "lesson", 4: "decision"}

DRAFTS_PER_RUN = 3
MAX_REWRITES = 3


class DraftRejected(RuntimeError):
    def __init__(self, problems: list[str], draft: str = ""):
        super().__init__("; ".join(problems))
        self.problems = problems
        self.draft = draft


# Two of the posts the owner approved on 2026-10-23 (round 2, posts 1 and 3). A written description of the shape alone produced step lists.
APPROVED_EXAMPLES = (Path(__file__).resolve().parents[2] / "data" / "approved_posts.txt").read_text(encoding="utf-8")


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

Shape (the structure the owner approved on 2026-10-23):
- First line: {hook} Keep it at most 135 characters and make it a complete claim on its own, because only the first line shows
  before "see more".
- Then short paragraphs of one to three sentences separated by blank lines, each leading to the next:
  why it mattered (only from YOUR OWN NOTES, at most one sentence), what you built, the turning point (the result or decision that
  changed how you read the work), and the measured result.
- Frame the work as an engineering decision a data or ML engineer would recognise. Keep any job-search backstory to one sentence.
- Plain words: every number says what it measures ("agreed on 6 of 8 resumes", not "6/8 alignment"). No slogans, no abstract claims.
- Tell it as a story with a question, a test and a finding, not as a list of steps. The question is the one the facts state;
  never give yourself a motive ("I needed to prove", "I wanted to make sure") or a quality word the numbers do not say
  ("perfect", "flawless", "reliable" for 124 of 124: write "all 124 runs passed"). Vary how paragraphs open: at most two start
  with "I", and no two paragraphs in a row start with the same words.
- Continuity: every paragraph answers a question the one before it raises, so a reader never feels the thread drop. Before the
  test, say in one sentence why it was needed (what could go wrong, what had to be proven). Open the test and result paragraphs
  with a link to what came before ("So I checked...", "That meant...", "The answer was..."), never with a bare "To test..." or a
  list of numbers. Give results as what they mean ("it named the right member every time, and missed one answer of 26"), with
  the number inside the sentence, not as a run of percentages. The decision follows from the result in the same breath.
- {ending}
- Total length {min_chars} to {max_chars} characters including spaces (at least 150 words), then one last line with 2 relevant
  hashtags.
- APPROVED EXAMPLES below show the shape and voice the owner approved. Copy their shape only: never their facts, numbers, tools or
  sentences.
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

# Every format ends the same way: one concrete closing line with the practical result. No closing question of any kind (owner's
# rule, 2026-10-22: a generic question read as filler); asking for likes or comments stays banned above.
_CLOSE = ("End with one short paragraph: one concrete sentence about what the work now lets you or its user do. Do not end with a "
          "question.")
ENDINGS = {fmt: _CLOSE for fmt in ("project_spotlight", "lesson", "decision", "news_take")}


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


STORY_RULES = """
STORY below is the one measured test this post is about. Build the whole post on it. The first paragraph must give the reader the
setting before any figure: what the project is and what it was built to do, in plain words, taken only from STORY's question and
FEATURED, then the most telling result. Never invent a reason, motivation, constraint, audience or "challenge" the facts do not state
(no "needed to fit on a free GPU", no "the hardest part was"); if the facts give no reason, say what the project does and move on
(never open on a bare result such as "A model reached 86% accuracy"; a reader who does not know the project cannot weigh it). Then
explain how it was tested, give the results, and end with the decision it led to. FEATURED only tells you what the project is; do not
add any other fact from FEATURED. Every number in the post must come from STORY, written as STORY writes it: never work out a new
number from them (no differences, totals, ratios or percentages STORY does not state), and never add a speed, size or scale claim
STORY does not make. Never round: write 0.9813 as 0.9813 or exactly as 98.13%, never as 98.1% or "about 98%".

STORY:
{story}
"""

FEEDBACK_RULES = """
The owner rejected earlier drafts with the comments below. Follow every one of them:
{feedback}
"""


def build_prompt(fmt: str, profile: dict, item: dict, hook_type: str, news: dict | None = None, story: dict | None = None,
                 feedback: list[str] | None = None) -> str:
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
    prompt += "\nAPPROVED EXAMPLES (shape only; none of these facts may appear in your post):\n" + APPROVED_EXAMPLES + "\n"
    if story:
        from app.services.story_bank import story_text

        prompt += STORY_RULES.format(story=story_text(story))
        if story.get("repeat_of"):
            prompt += (f"\nThis test was already posted on {story['repeat_of']}. Write it from a different angle: lead with a different "
                       "result or with the decision, and do not reuse the earlier opening.\n")
    if feedback:
        prompt += FEEDBACK_RULES.format(feedback="\n".join(f"- {f}" for f in feedback))
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
Do NOT count: rewording or paraphrase of a fact or of the owner's notes, a plain restatement of what a result means (for example
"only June's rows were read" from "3,015 of 60,000 rows read"), the author's opinion or lesson clearly phrased as an opinion ("I would make the same choice again",
"what I take from this"), general engineering advice to readers, a correct general explanation of how a named tool or technique works (for example "a Snowflake
Python UDF runs the model inside the warehouse"), a closing question, or a sentence saying the author is open to roles.
Also judge the reading flow, the way the owner reads: list as "flow" every place where the thread drops. That covers a paragraph
that does not follow from the one before it; a test described without saying why it was needed; results given as a run of
numbers without saying what they mean; and a decision that does not visibly follow from a result. The owner rejected a draft
whose third paragraph jumped to "To test how accurate..." and whose fourth listed three percentages.
Return only JSON: {{"unsupported": ["short description of each problem"], "flow": ["short description of each flow problem"]}}"""


async def critic_problems(text: str, facts: str, settings: Settings) -> list[str]:
    """Second-pass fact check by the model. Mechanical checks catch invented numbers and tools; this catches invented capabilities and
    misattributed results ("automated application submission", "this 60% came from the migration")."""
    import json
    import re

    try:
        raw = await call_llm_with_fallback(messages=[{"role": "user", "content": CRITIC_PROMPT.format(facts=facts, post=text)}],
                                           settings=settings, temperature=0.0, tier="write")
    except Exception as exc:
        # An unchecked draft is never published: if the fact check cannot run, the draft fails it.
        return [f"fact check could not run ({type(exc).__name__})"]
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    try:
        data = json.loads(raw)
        found, flow = data.get("unsupported", []), data.get("flow", [])
    except (ValueError, AttributeError):
        return ["fact check returned no readable answer"]
    return ([f"unsupported by the facts: {p}" for p in found if isinstance(p, str) and p.strip()] +
            [f"reading flow: {p}" for p in flow if isinstance(p, str) and p.strip()])


def _finish(text: str) -> str:
    return tidy_hashtags(humanize_draft(text))


def _rank(text: str) -> float:
    return abs(len(text) - (MIN_CHARS + MAX_CHARS) / 2)


async def _one_draft(prompt: str, settings: Settings) -> str:
    return _finish(await call_llm_with_fallback(messages=[{"role": "user", "content": prompt}], settings=settings, temperature=1.0,
                                                tier="write"))


async def generate_post(fmt: str, profile: dict, settings: Settings, day: date, news_items: list[dict] | None = None,
                        history: list[dict] | None = None, story: dict | None = None, item: dict | None = None,
                        feedback: list[str] | None = None) -> dict:
    """Write the day's post. Returns {text, subject, format, hook_type, item, attempts, story}; raises DraftRejected if nothing passes.
    With a story (and its project as item) the post is built on that one test and its numbers only."""
    history = history or []
    item = item or pick_subject(profile, fmt, history, day)
    news = None
    if fmt == "decision" and news_items and news_allowed(history):
        news = matching_news(item, news_items)
        if news:
            fmt = "news_take"
    if fmt == "decision" and not item.get("notes") and not story:
        # Why a decision was made can only come from the owner; without his notes a decision post would have to invent the reasons.
        fmt = "lesson"
    hook_type = pick_hook(item, history)
    prompt = build_prompt(fmt, profile, item, hook_type, news, story, feedback)
    facts = source_text(profile, item, news)
    story_facts = ""
    if story:
        from app.services.story_bank import story_text

        # The fact check sees the story, the project's facts and the owner's notes; numbers must come from the story alone.
        story_facts = story_text(story) + "\n" + profile_context(profile)
        # Labelled sections: an unlabelled block let the fact check miss that a motivation came from the owner's own notes.
        notes = "\n".join(f"- {n}" for n in item.get("notes", [])) or "(none)"
        facts = (f"STORY (the test this post is about):\n{story_text(story)}\n\nPROJECT FACTS:\n{format_item(item)}\n"
                 f"{item.get('context', '')}\n\nOWNER'S OWN NOTES (his own words on why he built it; motivation that matches these "
                 f"is supported):\n{notes}\n\nBACKGROUND:\n{profile_context(profile)}")

    def rule_problems(draft: str) -> list[str]:
        found = check_draft(draft, item, facts, history)
        if story_facts:
            found += [f"number {n} is not in the story" for n in unsupported_numbers(draft, story_facts)]
        return found
    logger.info("Drafting %s about %s (hook: %s)", fmt, item["title"], hook_type)

    results = await asyncio.gather(*(_one_draft(prompt, settings) for _ in range(DRAFTS_PER_RUN)), return_exceptions=True)
    drafts = [r for r in results if isinstance(r, str) and r.strip()]
    if not drafts:
        raise DraftRejected([f"no draft returned: {results[0]}"])
    checked = sorted(((d, rule_problems(d)) for d in drafts), key=lambda p: (len(p[1]), _rank(p[0])))
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
        best = _finish(await call_llm_with_fallback(messages=[{"role": "user", "content": fix}], settings=settings, temperature=0.7,
                                                    tier="write"))
        problems = rule_problems(best)
        attempts += 1
        if not problems:
            problems = await critic_problems(best, facts, settings)
            attempts += 1

    bad_numbers = [m.group(1) for p in problems for m in [re.search(r"number '?([^' ]+)'? is not in the", p)] if m]
    if problems and len(bad_numbers) == len(problems):
        # Rewrites kept a number the facts do not have; cut the sentences that state it and check the result again.
        repaired = _finish(drop_sentences_with_numbers(best, bad_numbers))
        if not rule_problems(repaired) and not await critic_problems(repaired, facts, settings):
            logger.info("Draft repaired by removing sentences with unsupported numbers: %s", bad_numbers)
            best, problems = repaired, []
        attempts += 1

    if problems:
        raise DraftRejected(problems, best)
    logger.info("Draft accepted", extra={"format": fmt, "chars": len(best), "attempts": attempts})
    return {"text": best, "subject": item["title"], "format": fmt, "hook_type": hook_type, "item": item, "attempts": attempts,
            "news": news, "story": story, "facts": facts}


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
