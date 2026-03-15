"""Respond node — send the formatted message via WhatsApp API."""

import logging

from langchain_core.runnables import RunnableConfig

from src.services.whatsapp import send_buttons, send_list, send_text

logger = logging.getLogger(__name__)


async def respond(state: dict, config: RunnableConfig) -> dict:
    """Send the response message via WhatsApp."""
    wa_id = state["wa_id"]
    response_type = state.get("response_type", "text")
    payload = state.get("response_payload", {})

    try:
        if response_type == "interactive_buttons":
            await send_buttons(wa_id, payload["body"], payload["buttons"])
        elif response_type == "interactive_list":
            await send_list(wa_id, payload["body"], payload["button_text"], payload["sections"])
        else:
            await send_text(wa_id, payload.get("body", "Something went wrong. Try again!"))
    except Exception:
        logger.exception("Failed to send WhatsApp message to %s", wa_id)

    return {}
