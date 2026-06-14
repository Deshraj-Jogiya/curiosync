"""Tests for the LLM model fallback service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import Settings
from app.services.llm_service import call_llm_with_fallback


@pytest.mark.asyncio
async def test_call_llm_with_fallback_success_first_try():
    settings = Settings(
        secret_key="test",
        database_url="sqlite+aiosqlite://",
        linkedin_client_id="test",
        linkedin_client_secret="test",
        fernet_key="On9Xt3DeuvikAzn4c-yVjMCAyVAJJXGvKAh6rOstuUU=",
        openai_api_key="test",
        openai_model="gemini-3.5-flash",
    )

    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_message = MagicMock()
    mock_message.content = "Draft response content"
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]

    mock_create = AsyncMock(return_value=mock_response)

    with patch("openai.resources.chat.completions.AsyncCompletions.create", mock_create):
        result = await call_llm_with_fallback(
            messages=[{"role": "user", "content": "hello"}],
            settings=settings,
        )
        assert result == "Draft response content"
        assert mock_create.call_count == 1
        mock_create.assert_called_with(
            model="gemini-3.5-flash",
            messages=[{"role": "user", "content": "hello"}],
            temperature=0.7,
        )


@pytest.mark.asyncio
async def test_call_llm_with_fallback_success_after_failure():
    settings = Settings(
        secret_key="test",
        database_url="sqlite+aiosqlite://",
        linkedin_client_id="test",
        linkedin_client_secret="test",
        fernet_key="On9Xt3DeuvikAzn4c-yVjMCAyVAJJXGvKAh6rOstuUU=",
        openai_api_key="test",
        openai_model="gemini-2.5-pro",
    )

    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_message = MagicMock()
    mock_message.content = "Draft response content"
    mock_choice.message = mock_message
    mock_response.choices = [mock_choice]

    mock_create = AsyncMock()
    mock_create.side_effect = [
        Exception("429 Too Many Requests"),
        mock_response,
    ]

    with patch("openai.resources.chat.completions.AsyncCompletions.create", mock_create):
        result = await call_llm_with_fallback(
            messages=[{"role": "user", "content": "hello"}],
            settings=settings,
        )
        assert result == "Draft response content"
        assert mock_create.call_count == 2
        # First call should try gemini-2.5-pro
        assert mock_create.call_args_list[0][1]["model"] == "gemini-2.5-pro"
        # Second call should try gemini-3.5-flash
        assert mock_create.call_args_list[1][1]["model"] == "gemini-3.5-flash"
