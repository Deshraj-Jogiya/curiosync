"""LLM utility service with model fallback handling.

Gemini's free tier allows about 20 requests a day per model, and one post draft takes 4-10 calls, so Groq (free tier, about 1,000
requests a day on its larger models, no card) is the second provider when GROQ_API_KEY is set. A model that answers 429 with a daily
quota error is skipped for the rest of the run instead of being retried on every call.
"""

import asyncio
import os
import re

import openai
from app.config import Settings
from app.utils.logging import logger

FALLBACK_MODELS = [
    "gemini-3.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash-lite",
    "gemini-2.5-flash"
]

GROQ_BASE = "https://api.groq.com/openai/v1"
# Text models this Groq key can use (listed by the upload-check run on 2026-10-26); each has its own daily allowance.
GROQ_STRONG = ["openai/gpt-oss-120b", "qwen/qwen3.8-27b"]
GROQ_LIGHT = ["openai/gpt-oss-20b"]
# Models good enough to write or fact-check a post. The flash-lite models wrote short, flat drafts, so a post waits for the next day
# rather than being written by one of them.
GEMINI_STRONG = ["gemini-3.5-flash", "gemini-2.5-flash"]

# (provider base, model) pairs that hit their daily quota during this run.
_exhausted: set[tuple[str | None, str]] = set()


def _per_minute_wait(err: Exception) -> float | None:
    """Seconds to wait when a model is only over its per-minute limit (Groq: "tokens per minute"), else None."""
    text = str(err)
    if "429" not in text or not re.search(r"per minute|TPM|RPM", text):
        return None
    m = re.search(r"try again in ([\d.]+)s", text)
    return min(60.0, float(m.group(1)) + 1) if m else 20.0


def _is_daily_quota(err: Exception) -> bool:
    text = str(err)
    return "429" in text and ("PerDay" in text or "per day" in text.lower() or "RESOURCE_EXHAUSTED" in text)


async def call_llm_with_fallback(
    messages: list[dict],
    settings: Settings,
    temperature: float = 0.7,
    tier: str = "any",
) -> str:
    """Call LLM completion API with automatic model fallback for 429/404 errors.

    tier "write" (drafting and fact-checking a post): strong models only, Gemini first, then Groq's strong models.
    tier "mine" (reading repository documents for stories): Groq's light model first, then the rest, so mining does not spend the
    strong models' allowance. tier "any": the configured model, Groq's models, then the remaining FALLBACK_MODELS.
    """
    api_base = settings.openai_api_base
    if isinstance(api_base, str):
        api_base = api_base.strip()
    if not api_base:
        # Default to Gemini endpoint unless it's a standard OpenAI 'sk-' key
        if settings.openai_api_key and settings.openai_api_key.startswith("sk-"):
            api_base = None
        else:
            api_base = "https://generativelanguage.googleapis.com/v1beta/openai/"
            logger.info("Defaulting API base to Google AI Studio for Gemini.")

    configured_model = settings.openai_model
    gemini_all = [configured_model] + [m for m in FALLBACK_MODELS if m != configured_model]
    groq_key = os.getenv("GROQ_API_KEY", "").strip()

    def gem(models):
        return [(api_base, settings.openai_api_key, m) for m in models]

    def groq(models):
        return [(GROQ_BASE, groq_key, m) for m in models] if groq_key else []

    if tier == "write":
        strong = [configured_model] + [m for m in GEMINI_STRONG if m != configured_model]
        attempts = gem(strong) + groq(GROQ_STRONG)
    elif tier == "mine":
        attempts = groq(GROQ_LIGHT) + groq(GROQ_STRONG) + gem([m for m in gemini_all if m not in GEMINI_STRONG]) + gem(GEMINI_STRONG)
    else:
        attempts = gem([configured_model]) + groq(GROQ_STRONG + GROQ_LIGHT) + gem(gemini_all[1:])

    clients: dict[tuple[str | None, str], openai.AsyncOpenAI] = {}
    last_error = None
    for base, key, model in attempts:
        if (base, model) in _exhausted:
            continue
        client = clients.get((base, key))
        if client is None:
            client = clients[(base, key)] = openai.AsyncOpenAI(api_key=key, base_url=base, timeout=45.0)
        try:
            logger.info("Attempting LLM call with model: %s", model)
            extra = {}
            if model.startswith("openai/gpt-oss"):
                # gpt-oss reasons before answering; on long documents the reasoning used the whole reply budget and the answer came
                # back empty. Short reasoning and a larger budget leave room for the answer.
                extra = {"max_tokens": 8000, "extra_body": {"reasoning_effort": "low"}}
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                timeout=90.0,
                **extra,
            )
            content = (response.choices[0].message.content or "").strip()
            if not content:
                raise ValueError(f"empty reply from {model}")
            logger.info("LLM call succeeded with model: %s", model)
            return content
        except Exception as e:
            wait = _per_minute_wait(e)
            if wait is not None:
                # Over the per-minute limit only: wait it out once and try the same model again.
                logger.info("Model %s is over its per-minute limit; waiting %.0f s", model, wait)
                await asyncio.sleep(wait)
                try:
                    response = await client.chat.completions.create(model=model, messages=messages, temperature=temperature,
                                                                    timeout=90.0, **extra)
                    content = (response.choices[0].message.content or "").strip()
                    if content:
                        logger.info("LLM call succeeded with model: %s", model)
                        return content
                except Exception as retry_error:
                    e = retry_error
            if _is_daily_quota(e):
                _exhausted.add((base, model))
                logger.warning("Model %s is out of its daily quota; skipping it for the rest of this run.", model)
            else:
                logger.warning("LLM call failed with model %s: %s. Trying next fallback...", model, str(e)[:300])
            last_error = e
            continue

    logger.error("All LLM models in the fallback chain failed.")
    raise last_error or Exception("All LLM models failed to generate a response.")
