"""LLM utility service with model fallback handling."""

import openai
from app.config import Settings
from app.utils.logging import logger

FALLBACK_MODELS = [
    "gemini-3.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-2.0-flash-lite",
    "gemini-2.5-flash"
]


async def call_llm_with_fallback(
    messages: list[dict],
    settings: Settings,
    temperature: float = 0.7,
) -> str:
    """Call LLM completion API with automatic model fallback for 429/404 errors.

    Attempts configured model first, then cycles through FALLBACK_MODELS.
    """
    configured_model = settings.openai_model
    models_to_try = [configured_model]
    for m in FALLBACK_MODELS:
        if m not in models_to_try:
            models_to_try.append(m)

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

    client = openai.AsyncOpenAI(
        api_key=settings.openai_api_key,
        base_url=api_base,
    )

    last_error = None
    for model in models_to_try:
        try:
            logger.info("Attempting LLM call with model: %s", model)
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temperature,
            )
            logger.info("LLM call succeeded with model: %s", model)
            return response.choices[0].message.content.strip()
        except Exception as e:
            logger.warning(
                "LLM call failed with model %s: %s. Trying next fallback...",
                model,
                str(e)
            )
            last_error = e
            continue

    logger.error("All LLM models in the fallback chain failed.")
    raise last_error or Exception("All LLM models failed to generate a response.")
