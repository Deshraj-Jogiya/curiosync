"""Tests for the image generation service."""

import os
from app.services.image_service import parse_draft_for_image, generate_linkedin_image


def test_parse_draft_for_image():
    draft_text = (
        "Enterprise AI and Governance Strategy\n\n"
        "Here are the core insights of today:\n"
        "* Anthropic suspended models due to U.S. directives.\n"
        "* KPMG retracted report due to hallucinations.\n"
        "* OpenAI faces state-level investigations.\n\n"
        "#AIGovernance #MachineLearning"
    )
    title, bullets = parse_draft_for_image(draft_text)
    assert title == "Enterprise AI and Governance Strategy"
    assert len(bullets) == 3
    assert bullets[0] == "Anthropic suspended models due to U.S. directives."
    assert bullets[1] == "KPMG retracted report due to hallucinations."
    assert bullets[2] == "OpenAI faces state-level investigations."


def test_generate_linkedin_image():
    title = "Test AI Strategy Title"
    bullets = ["Factual point one.", "Factual point two."]

    filepath = generate_linkedin_image(title, bullets, "Test Subtitle")
    assert os.path.exists(filepath)
    assert filepath.endswith(".png")

    # Clean up
    if os.path.exists(filepath):
        os.remove(filepath)
