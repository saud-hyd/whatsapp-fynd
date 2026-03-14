"""Extract listing node — stub for Phase 3."""

from langgraph.types import Command


async def extract_listing(state: dict, config: dict) -> Command:
    """Extract listing details from user message. (Phase 3 — stub.)"""
    return Command(
        goto="respond",
        update={
            "response_type": "text",
            "response_payload": {
                "body": "Listing extraction is coming soon! Stay tuned.",
            },
        },
    )
