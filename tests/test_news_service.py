"""Tests for the news service."""

from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import pytest

from app.services.news_service import _parse_published, _is_today, RSS_FEEDS, SOURCE_CREDIBILITY
from app.utils.timezone import today_phoenix


class TestParsePublished:
    def test_parses_published_parsed(self):
        entry = {"published_parsed": (2026, 6, 13, 10, 0, 0, 0, 0, 0)}
        result = _parse_published(entry)
        assert isinstance(result, datetime)
        assert result.year == 2026
        assert result.month == 6

    def test_parses_updated_parsed_fallback(self):
        entry = {"updated_parsed": (2026, 6, 13, 10, 0, 0, 0, 0, 0)}
        result = _parse_published(entry)
        assert isinstance(result, datetime)

    def test_returns_none_for_missing(self):
        entry = {}
        result = _parse_published(entry)
        assert result is None


class TestIsToday:
    def test_today_returns_true(self):
        today = today_phoenix()
        dt = datetime(today.year, today.month, today.day, 12, 0)
        assert _is_today(dt, today) is True

    def test_yesterday_returns_false(self):
        today = today_phoenix()
        yesterday = datetime(today.year, today.month, today.day, 12, 0) - timedelta(days=1)
        assert _is_today(yesterday, today) is False

    def test_none_returns_true(self):
        """Items with unknown dates are included (err on side of inclusion)."""
        today = today_phoenix()
        assert _is_today(None, today) is True


class TestRSSFeedsConfig:
    def test_has_multiple_feeds(self):
        assert len(RSS_FEEDS) >= 5

    def test_feed_urls_are_strings(self):
        for name, url in RSS_FEEDS.items():
            assert isinstance(url, str)
            assert url.startswith("http")

    def test_source_credibility_defined(self):
        for name in RSS_FEEDS:
            assert name in SOURCE_CREDIBILITY
            assert 0 < SOURCE_CREDIBILITY[name] <= 1.0
