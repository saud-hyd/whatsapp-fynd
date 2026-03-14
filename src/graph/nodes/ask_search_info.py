"""Ask search info node — ask for missing city or seeker intro, then re-route to search."""

import logging

from langgraph.types import Command, interrupt

logger = logging.getLogger(__name__)


async def ask_search_info(state: dict, config: dict) -> Command:
    """Send the question (already in response_payload) and wait for answer via interrupt."""
    question = state.get("response_payload", {}).get("body", "Could you tell me more?")

    # Single deterministic interrupt
    answer = interrupt(question)

    logger.info("Search info answer: %s", answer)

    # Add the answer to messages and re-route to search_and_match
    return Command(
        goto="search_and_match",
        update={"messages": [{"role": "user", "content": answer}]},
    )
