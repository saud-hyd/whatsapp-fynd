"""Tests for the LangGraph state and node logic."""

from src.graph.state import FyndState


class TestFyndState:
    def test_state_has_required_keys(self):
        """FyndState should accept all required fields."""
        state: FyndState = {
            "messages": [],
            "wa_id": "4917612345678",
            "user_id": None,
            "user_role": None,
            "intent": None,
            "extracted_listing": None,
            "extracted_preferences": None,
            "match_results": None,
            "response_type": "text",
            "response_payload": {},
        }
        assert state["wa_id"] == "4917612345678"
        assert state["messages"] == []
        assert state["response_type"] == "text"

    def test_state_messages_field_exists(self):
        """Verify messages field is annotated (add_messages reducer)."""
        import typing

        hints = typing.get_type_hints(FyndState, include_extras=True)
        messages_hint = hints["messages"]
        # Check it's Annotated (has __metadata__)
        assert hasattr(messages_hint, "__metadata__"), (
            "messages must use Annotated[list, add_messages] reducer"
        )
