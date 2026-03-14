"""Tests for intent classification model."""

import pytest
from pydantic import ValidationError

from src.models.intent import ClassifiedIntent


class TestClassifiedIntent:
    def test_valid_intent(self):
        intent = ClassifiedIntent(intent="list_place", confidence=0.95)
        assert intent.intent == "list_place"
        assert intent.confidence == 0.95

    def test_all_valid_intents(self):
        valid_intents = [
            "onboard",
            "list_place",
            "search_place",
            "opt_in_response",
            "update_listing",
            "help",
            "unknown",
        ]
        for name in valid_intents:
            intent = ClassifiedIntent(intent=name, confidence=0.5)
            assert intent.intent == name

    def test_invalid_intent_rejected(self):
        with pytest.raises(ValidationError):
            ClassifiedIntent(intent="invalid_intent", confidence=0.5)

    def test_confidence_must_be_between_0_and_1(self):
        with pytest.raises(ValidationError):
            ClassifiedIntent(intent="greeting", confidence=1.5)
        with pytest.raises(ValidationError):
            ClassifiedIntent(intent="greeting", confidence=-0.1)

    def test_confidence_boundary_values(self):
        assert ClassifiedIntent(intent="help", confidence=0.0).confidence == 0.0
        assert ClassifiedIntent(intent="help", confidence=1.0).confidence == 1.0
