"""Tests for prompt definitions — ensure they exist and are non-empty."""

from src.graph import prompts


class TestPrompts:
    def test_intent_classification_prompt_exists(self):
        assert len(prompts.INTENT_CLASSIFICATION) > 50
        assert "list_place" in prompts.INTENT_CLASSIFICATION
        assert "search_place" in prompts.INTENT_CLASSIFICATION

    def test_onboard_message_exists(self):
        assert len(prompts.ONBOARD_MESSAGE) > 20
        assert "Fynd" in prompts.ONBOARD_MESSAGE

    def test_help_message_exists(self):
        assert len(prompts.HELP_MESSAGE) > 50
        assert "place" in prompts.HELP_MESSAGE.lower()

    def test_listing_extraction_prompt_exists(self):
        assert len(prompts.LISTING_EXTRACTION) > 50
        assert "rent_amount" in prompts.LISTING_EXTRACTION

    def test_search_extraction_prompt_exists(self):
        assert len(prompts.SEARCH_EXTRACTION) > 50
        assert "max_rent" in prompts.SEARCH_EXTRACTION

    def test_match_reason_prompt_exists(self):
        assert len(prompts.MATCH_REASON) > 20
