"""Follow-up node — ask for one missing field using interrupt, then re-extract."""

import logging

from langchain_core.messages import SystemMessage
from langgraph.types import Command, interrupt

from src.graph.prompts import FOLLOW_UP_FIELD
from src.models.listing import ExtractedListing
from src.services.gemini import get_llm

logger = logging.getLogger(__name__)

FIELD_LABELS = {
    "city": "city",
    "rent_amount": "monthly rent",
    "rooms": "number of rooms",
    "available_from": "availability date",
}


async def follow_up(state: dict, config: dict) -> Command:
    """Ask for the first missing required field, then route back to extract_listing."""
    listing = ExtractedListing(**state["extracted_listing"])
    missing = listing.missing_required_fields()

    if not missing:
        # Nothing missing — go to confirmation
        return Command(goto="confirm_listing")

    field = missing[0]
    label = FIELD_LABELS.get(field, field)

    # Generate a natural question
    llm = get_llm()
    prompt = FOLLOW_UP_FIELD.format(field_name=label)
    question_resp = await llm.ainvoke([SystemMessage(content=prompt), *state["messages"]])

    # Single interrupt — deterministic, always exactly one per invocation
    answer = interrupt(question_resp.content)

    logger.info("Follow-up answer for %s: %s", field, answer)

    # Route back to extract_listing — the resumed answer is now in messages
    # via main.py adding HumanMessage on resume
    return Command(
        goto="extract_listing",
        update={"messages": [{"role": "user", "content": answer}]},
    )
