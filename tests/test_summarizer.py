"""Tests for the summarizer service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.summarizer_service import (
    LINKEDIN_POST_PROMPT,
    _format_news_for_prompt,
    validate_draft_length,
)


class TestFormatNewsForPrompt:
    def test_formats_numbered_list(self, mock_news_items):
        result = _format_news_for_prompt(mock_news_items[:3])
        assert "1. [TechCrunch]" in result
        assert "2. [Ars Technica]" in result
        assert "3. [The Verge]" in result

    def test_includes_title(self, mock_news_items):
        result = _format_news_for_prompt(mock_news_items[:1])
        assert "GPT-5" in result

    def test_includes_summary(self, mock_news_items):
        result = _format_news_for_prompt(mock_news_items[:1])
        assert "reasoning" in result.lower()

    def test_truncates_long_summary(self):
        items = [{"title": "Test", "source_name": "Test", "summary": "x" * 300}]
        result = _format_news_for_prompt(items)
        # Summary should be truncated to 200 chars
        lines = result.split("\n")
        summary_line = [l for l in lines if l.startswith("   ")][0]
        assert len(summary_line.strip()) <= 200


class TestValidateDraftLength:
    def test_valid_length(self):
        text = " ".join(["word"] * 150)
        valid, count = validate_draft_length(text)
        assert valid is True
        assert count == 150

    def test_too_short(self):
        text = " ".join(["word"] * 100)
        valid, count = validate_draft_length(text)
        assert valid is False
        assert count == 100

    def test_too_long(self):
        text = " ".join(["word"] * 400)
        valid, count = validate_draft_length(text)
        assert valid is False
        assert count == 400

    def test_lower_boundary(self):
        text = " ".join(["word"] * 150)
        valid, _ = validate_draft_length(text)
        assert valid is True

    def test_upper_boundary(self):
        text = " ".join(["word"] * 300)
        valid, _ = validate_draft_length(text)
        assert valid is True


class TestPromptTemplate:
    def test_prompt_contains_key_instructions(self):
        assert "220 to 320 words" in LINKEDIN_POST_PROMPT
        assert "ONLY the provided news items" in LINKEDIN_POST_PROMPT
        assert "senior" in LINKEDIN_POST_PROMPT.lower()
        assert "bullet" in LINKEDIN_POST_PROMPT.lower()
        assert "hashtag" in LINKEDIN_POST_PROMPT.lower()

    def test_prompt_has_placeholder(self):
        assert "{news_items}" in LINKEDIN_POST_PROMPT
