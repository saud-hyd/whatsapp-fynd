from typing import Annotated

from langgraph.graph.message import AnyMessage, add_messages
from typing_extensions import TypedDict


class FyndState(TypedDict):
    """State for the WhatsApp Fynd conversation graph."""

    # Conversation history — add_messages reducer appends instead of replacing
    messages: Annotated[list[AnyMessage], add_messages]

    # User context
    wa_id: str
    user_id: str | None
    user_role: str | None  # 'lister' | 'seeker' | 'both' | None

    # Classified intent for routing
    intent: str | None

    # Extraction results
    extracted_listing: dict | None
    extracted_preferences: dict | None

    # Match results
    match_results: list | None

    # Current match index for one-at-a-time display
    current_match_index: int | None

    # Response to send back via WhatsApp
    response_type: str | None  # 'text' | 'interactive_buttons' | 'interactive_list'
    response_payload: dict | None
