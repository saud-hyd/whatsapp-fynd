"""Identify user node — lookup by wa_id, create if new."""

import logging

from langgraph.types import Command

from src.services.supabase import create_user, get_user_by_wa_id

logger = logging.getLogger(__name__)


async def identify_user(state: dict, config: dict, *, store) -> Command:
    """Look up the user by WhatsApp ID. Create a new user if not found."""
    wa_id = state["wa_id"]
    conn = config["configurable"]["conn"]

    user = await get_user_by_wa_id(conn, wa_id)

    if user is None:
        user = await create_user(conn, wa_id)
        logger.info("New user created: %s", wa_id)

    return Command(
        goto="classify_intent",
        update={
            "user_id": str(user["id"]),
            "user_role": user.get("role"),
        },
    )
