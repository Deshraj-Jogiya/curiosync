"""Tests for the compliance service."""

from app.services.compliance_service import humanize_draft, check_compliance


class TestHumanizeDraft:
    def test_removes_robotic_phrase(self):
        text = "In conclusion, this is a great day for tech."
        result = humanize_draft(text)
        assert "In conclusion" not in result
        assert "To sum up" in result

    def test_replaces_game_changer(self):
        text = "This update is a real game-changer for developers."
        result = humanize_draft(text)
        assert "game-changer" not in result
        assert "significant development" in result

    def test_replaces_leverage(self):
        text = "Companies should leverage AI for productivity."
        result = humanize_draft(text)
        assert "leverage" not in result
        assert "use" in result

    def test_removes_lets_dive_in(self):
        text = "Let's dive in to today's tech news."
        result = humanize_draft(text)
        assert "Let's dive in" not in result

    def test_cleans_double_spaces(self):
        text = "Without further ado  here is the news."
        result = humanize_draft(text)
        assert "  " not in result

    def test_no_changes_for_clean_text(self):
        text = "Today's tech landscape saw meaningful developments in AI and cloud computing."
        result = humanize_draft(text)
        assert result == text

    def test_case_insensitive_replacement(self):
        text = "IN CONCLUSION, this is important."
        result = humanize_draft(text)
        assert "IN CONCLUSION" not in result

    def test_cleans_special_and_alien_characters(self):
        text = "OpenAI\ufffds new models and Meta\u2019s acquisition are \u201cgame-changers\u201d."
        result = humanize_draft(text)
        # Check replacement char resolved to apostrophe
        assert "OpenAI's" in result
        # Check curly quote resolved to apostrophe
        assert "Meta's" in result
        # Check curly double quotes resolved to straight double quotes
        assert '"' in result
        # Check game-changer robotic phrase also replaced
        assert "significant development" in result


class TestCheckCompliance:
    def test_valid_draft_passes(self):
        text = " ".join(["word"] * 150)
        result = check_compliance(text, [])
        assert result["passed"] is True
        assert result["issues"] == []

    def test_too_short_fails(self):
        text = " ".join(["word"] * 50)
        result = check_compliance(text, [])
        assert result["passed"] is False
        assert any("short" in issue.lower() for issue in result["issues"])

    def test_too_long_fails(self):
        text = " ".join(["word"] * 200)
        result = check_compliance(text, [])
        assert result["passed"] is False
        assert any("long" in issue.lower() for issue in result["issues"])

    def test_credential_language_fails(self):
        text = " ".join(["word"] * 150) + " Please enter your password to continue."
        result = check_compliance(text, [])
        assert result["passed"] is False
        assert any("credential" in issue.lower() for issue in result["issues"])

    def test_scraping_language_fails(self):
        text = " ".join(["word"] * 150) + " Use web scraping to gather data automatically."
        result = check_compliance(text, [])
        assert result["passed"] is False
        assert any("scraping" in issue.lower() for issue in result["issues"])

    def test_character_limit(self):
        text = "a " * 2000
        result = check_compliance(text, [])
        assert result["passed"] is False
        assert any("character" in issue.lower() for issue in result["issues"])
