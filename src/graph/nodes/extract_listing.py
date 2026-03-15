"""Extract listing node — Gemini extracts structured data, routes to follow-up or confirm."""

import logging

from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from src.graph.prompts import LISTING_EXTRACTION
from src.models.listing import ExtractedListing
from src.services.gemini import get_llm

logger = logging.getLogger(__name__)


async def extract_listing(state: dict, config: RunnableConfig) -> Command:
    """Extract listing fields from conversation. Routes to follow_up or confirm_listing."""
    llm = get_llm()
    extractor = llm.with_structured_output(ExtractedListing)
    messages = [SystemMessage(content=LISTING_EXTRACTION), *state["messages"]]
    result = await extractor.ainvoke(messages)

    # If we have a previous extraction, merge (keep old values where new is None)
    existing = state.get("extracted_listing")
    if existing:
        merged = ExtractedListing(**existing)
        for field_name in result.model_fields:
            new_val = getattr(result, field_name)
            if new_val is not None and new_val != [] and new_val != "":
                setattr(merged, field_name, new_val)
        result = merged

    logger.info("Extracted listing: %s", result.model_dump())

    listing_data = result.model_dump()
    missing = result.missing_required_fields()

    if missing:
        # Route to follow_up to ask for the first missing field
        return Command(
            goto="follow_up",
            update={"extracted_listing": listing_data},
        )

    # All required fields present — route to confirmation
    return Command(
        goto="confirm_listing",
        update={"extracted_listing": listing_data},
    )
