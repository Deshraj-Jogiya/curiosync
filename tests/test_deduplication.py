"""Tests for the deduplication service."""

from app.services.deduplication_service import deduplicate_news, generate_dedup_hash


class TestGenerateDedupHash:
    def test_identical_titles_same_hash(self):
        assert generate_dedup_hash("OpenAI launches GPT-5") == generate_dedup_hash("OpenAI launches GPT-5")

    def test_case_insensitive(self):
        assert generate_dedup_hash("OpenAI Launches GPT-5") == generate_dedup_hash("openai launches gpt-5")

    def test_punctuation_ignored(self):
        assert generate_dedup_hash("OpenAI launches GPT-5!") == generate_dedup_hash("OpenAI launches GPT-5")

    def test_word_order_independent(self):
        assert generate_dedup_hash("GPT-5 launches OpenAI") == generate_dedup_hash("OpenAI launches GPT-5")

    def test_different_titles_different_hash(self):
        assert generate_dedup_hash("OpenAI launches GPT-5") != generate_dedup_hash("Apple unveils M5 chip")


class TestDeduplicateNews:
    def test_empty_list(self):
        assert deduplicate_news([]) == []

    def test_no_duplicates(self):
        items = [
            {"title": "OpenAI launches GPT-5", "relevance_score": 1.0},
            {"title": "Apple unveils M5 chip", "relevance_score": 1.0},
            {"title": "EU passes AI regulation", "relevance_score": 0.8},
        ]
        result = deduplicate_news(items)
        assert len(result) == 3

    def test_exact_duplicate_removed(self):
        items = [
            {"title": "OpenAI launches GPT-5", "relevance_score": 1.0},
            {"title": "OpenAI launches GPT-5", "relevance_score": 0.8},
        ]
        result = deduplicate_news(items)
        assert len(result) == 1
        assert result[0]["relevance_score"] == 1.0

    def test_near_duplicate_removed(self):
        items = [
            {"title": "OpenAI launches GPT-5 with improved reasoning", "relevance_score": 0.8},
            {"title": "OpenAI launches GPT-5 with better reasoning capabilities", "relevance_score": 1.0},
        ]
        result = deduplicate_news(items)
        assert len(result) == 1
        # Higher credibility version kept
        assert result[0]["relevance_score"] == 1.0

    def test_distinct_stories_preserved(self):
        items = [
            {"title": "OpenAI launches GPT-5 with improved reasoning", "relevance_score": 1.0},
            {"title": "Apple unveils new M5 chip with 40% gains", "relevance_score": 1.0},
            {"title": "EU passes comprehensive AI regulation", "relevance_score": 0.8},
        ]
        result = deduplicate_news(items)
        assert len(result) == 3

    def test_large_list_with_mixed_duplicates(self, mock_news_items):
        # Add a near-duplicate
        items = mock_news_items + [
            {
                "title": "OpenAI unveils GPT-5 with improved reasoning and logic",
                "url": "https://other-site.com/gpt5",
                "source_name": "Other",
                "summary": "Same story different source",
                "published_at": None,
                "relevance_score": 0.5,
            }
        ]
        result = deduplicate_news(items)
        assert len(result) <= len(mock_news_items)
