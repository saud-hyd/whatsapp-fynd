"""Handle opt-in node — stub for Phase 4."""

from langgraph.types import Command


async def handle_opt_in(state: dict, config: dict) -> Command:
    """Handle double opt-in accept/reject flow. (Phase 4 — stub.)"""
    return Command(
        goto="respond",
        update={
            "response_type": "text",
            "response_payload": {
                "body": "Opt-in handling is coming soon! Stay tuned.",
            },
        },
    )
