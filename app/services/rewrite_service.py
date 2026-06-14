"""Draft rewriting service with tone adjustment."""

import openai

from app.config import Settings
from app.services.llm_service import call_llm_with_fallback
from app.utils.logging import logger

TONE_PROMPTS: dict[str, str] = {
    "professional": (
        "Rewrite the draft to sound highly polished, executive-level, and structured (resembling a formal data architecture report). Maintain a strict limit of 120-180 words. Keep all core facts."
    ),
    "simple": (
        "Simplify the vocabulary and sentence structures while keeping a clean executive format. Maintain a strict limit of 120-180 words. Keep all core facts."
    ),
    "shorter": (
        "Make this draft as concise and crisp as possible. Cut all filler words. Maintain a strict limit of 120-140 words. Keep all core facts."
    ),
    "more_engaging": (
        "Make this draft more engaging and thought-provoking to spark discussion, while maintaining the analytical and executive tone. Maintain a strict limit of 120-180 words. Keep all core facts."
    ),
    "more_technical": (
        "Use more precise data engineering, ETL, and AI/ML system terminology where appropriate (e.g. system pipelines, model latency, validation frameworks) to showcase deep technical expertise. Maintain a strict limit of 120-180 words. Keep all core facts."
    ),
}


def _build_rewrite_prompt(draft_text: str, tone: str, sources: list[dict]) -> str:
    """Assemble the rewrite prompt with original draft, tone instruction, and source context."""
    tone_instruction = TONE_PROMPTS.get(tone, TONE_PROMPTS["professional"])

    source_context = "\n".join(
        f"- [{s.get('source_name', '')}] {s.get('title', '')}" for s in sources
    )

    style_rules = (
        "Strict Formatting Rules:\n"
        "- Do NOT use sensational language, hype, or dramatic words (e.g., 'vaporize', 'dead', 'fault line').\n"
        "- Do NOT use rhetorical or engagement-bait questions at the beginning or end of the post. Write direct statements of fact or analysis instead.\n"
        "- Do NOT use any emojis.\n"
        "- Keep the tone objective, structured, direct, and factual (matching a formal data architecture report style).\n"
        "- Maintain a strict limit of 120-180 words."
    )

    return (
        f"{tone_instruction}\n\n"
        f"{style_rules}\n\n"
        f"Original draft:\n{draft_text}\n\n"
        f"Source articles for fact-checking:\n{source_context}\n\n"
        "Return ONLY the rewritten post text, nothing else."
    )


async def rewrite_draft(
    draft_text: str,
    tone: str,
    sources: list[dict],
    settings: Settings,
) -> str:
    """Rewrite an existing draft with a different tone using OpenAI."""
    prompt = _build_rewrite_prompt(draft_text, tone, sources)

    logger.info("Rewriting draft", extra={"tone": tone, "model": settings.openai_model})

    text = await call_llm_with_fallback(
        messages=[{"role": "user", "content": prompt}],
        settings=settings,
        temperature=0.7,
    )
    logger.info("Draft rewritten", extra={"tone": tone, "word_count": len(text.split())})
    return text
