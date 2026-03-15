"""Onboard user node — welcome message with role buttons (ambiguous intent fallback)."""

from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from src.graph.prompts import ONBOARD_MESSAGE


async def onboard_user(state: dict, config: RunnableConfig) -> Command:
    """Send welcome message with action buttons. Used when intent is ambiguous."""
    return Command(
        goto="respond",
        update={
            "response_type": "interactive_buttons",
            "response_payload": {
                "body": ONBOARD_MESSAGE,
                "buttons": [
                    {"id": "action_list", "title": "I have a place"},
                    {"id": "action_search", "title": "I need a place"},
                ],
            },
        },
    )
