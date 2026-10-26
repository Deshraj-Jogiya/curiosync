"""LLM utility service with model fallback handling.

Gemini's free tier allows about 20 requests a day per model, and one post draft takes 4-10 calls, so Groq (free tier, about 1,000
requests a day on its larger models, no card) is the second provider when GROQ_API_KEY is set. A model that answers 429 with a daily
quota error is skipped for the rest of the run instead of being retried on every call.
"""

import os

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
# Tried right after the configured Gemini model, before the weaker flash-lite models.
GROQ_MODELS = ["openai/gpt-oss-120b", "llama-3.3-70b-versatile"]

# (provider base, model) pairs that hit their daily quota during this run.
_exhausted: set[tuple[str | None, str]] = set()


def _is_daily_quota(err: Exception) -> bool:
    text = str(err)
    return "429" in text and ("PerDay" in text or "per day" in text.lower() or "RESOURCE_EXHAUSTED" in text)


async def call_llm_with_fallback(
    messages: list[dict],
    settings: Settings,
    temperature: float = 0.7,
) -> str:
    """Call LLM completion API with automatic model fallback for 429/404 errors.

    Attempts configured model first, then Groq's models (when GROQ_API_KEY is set), then the remaining FALLBACK_MODELS.
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
    primary = [(api_base, settings.openai_api_key, configured_model)]
    rest = [(api_base, settings.openai_api_key, m) for m in FALLBACK_MODELS if m != configured_model]
    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    groq = [(GROQ_BASE, groq_key, m) for m in GROQ_MODELS] if groq_key else []
    attempts = primary + groq + rest

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
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
                timeout=45.0,
            )
            logger.info("LLM call succeeded with model: %s", model)
            return response.choices[0].message.content.strip()
        except Exception as e:
            if _is_daily_quota(e):
                _exhausted.add((base, model))
                logger.warning("Model %s is out of its daily quota; skipping it for the rest of this run.", model)
            else:
                logger.warning("LLM call failed with model %s: %s. Trying next fallback...", model, str(e)[:300])
            last_error = e
            continue

    logger.error("All LLM models in the fallback chain failed.")
    raise last_error or Exception("All LLM models failed to generate a response.")
