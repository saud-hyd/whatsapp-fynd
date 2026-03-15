"""Confirm listing node — show summary, ask user to confirm or edit."""

import logging

from langchain_core.runnables import RunnableConfig
from langgraph.types import Command, interrupt

from src.models.listing import ExtractedListing
from src.services.embeddings import generate_embedding
from src.services.supabase import insert_listing, update_user_role

logger = logging.getLogger(__name__)


async def confirm_listing(state: dict, config: RunnableConfig) -> Command:
    """Show listing confirmation and wait for user decision."""
    conn = config["configurable"]["conn"]
    listing = ExtractedListing(**state["extracted_listing"])

    # Single deterministic interrupt — always exactly one
    confirmation = listing.format_confirmation()
    response = interrupt(confirmation)

    if response in ("action_confirm", "Looks good"):
        # Save the listing
        raw_text = ""
        for msg in state["messages"]:
            if hasattr(msg, "content") and msg.type == "human":
                raw_text += msg.content + "\n"
        raw_text = raw_text.strip()

        embedding = await generate_embedding(listing.summary, "RETRIEVAL_DOCUMENT")

        listing_data = {
            "user_id": state["user_id"],
            "raw_text": raw_text,
            "embedding": embedding,
            **listing.model_dump(exclude={"summary"}),
            "summary": listing.summary,
        }

        result = await insert_listing(conn, listing_data)
        logger.info("Listing saved: %s", result["id"])

        if not state.get("user_role"):
            await update_user_role(conn, state["user_id"], "lister")

        return Command(
            goto="respond",
            update={
                "extracted_listing": listing.model_dump(),
                "user_role": state.get("user_role") or "lister",
                "response_type": "text",
                "response_payload": {
                    "body": "Your listing is live! I'll let you know when someone's interested.",
                },
            },
        )

    # User wants to edit — add their edit message to context, re-extract
    return Command(
        goto="extract_listing",
        update={"messages": [{"role": "user", "content": response}]},
    )
