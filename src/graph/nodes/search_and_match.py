"""Search and match node — stub for Phase 3."""

from langgraph.types import Command


async def search_and_match(state: dict, config: dict) -> Command:
    """Search for matching listings. (Phase 3 — stub.)"""
    return Command(
        goto="respond",
        update={
            "response_type": "text",
            "response_payload": {
                "body": "Search & matching is coming soon! Stay tuned.",
            },
        },
    )
