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
        assert "do NOT assume" in prompts.LISTING_EXTRACTION

    def test_search_extraction_prompt_exists(self):
        assert len(prompts.SEARCH_EXTRACTION) > 50
        assert "max_rent" in prompts.SEARCH_EXTRACTION
        assert "seeker_intro" in prompts.SEARCH_EXTRACTION

    def test_match_reason_prompt_exists(self):
        assert len(prompts.MATCH_REASON) > 20
        assert "honest" in prompts.MATCH_REASON.lower()

    def test_follow_up_field_prompt_exists(self):
        assert len(prompts.FOLLOW_UP_FIELD) > 20
        assert "{field_name}" in prompts.FOLLOW_UP_FIELD

    def test_seeker_intro_request_prompt_exists(self):
        assert len(prompts.SEEKER_INTRO_REQUEST) > 20

    def test_listing_update_merge_prompt_exists(self):
        assert len(prompts.LISTING_UPDATE_MERGE) > 20
        assert "{current_listing}" in prompts.LISTING_UPDATE_MERGE

    def test_no_berlin_default_in_extraction_prompts(self):
        listing_prompt = prompts.LISTING_EXTRACTION
        search_prompt = prompts.SEARCH_EXTRACTION
        assert "do NOT assume" in listing_prompt
        assert "do NOT assume" in search_prompt
