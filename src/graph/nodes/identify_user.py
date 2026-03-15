"""Identify user node — lookup by wa_id, create if new, flush pending notifications."""

import logging

from langchain_core.runnables import RunnableConfig
from langgraph.store.base import BaseStore
from langgraph.types import Command

from src.services.notifications import flush_pending_notifications, update_last_active
from src.services.supabase import create_user, get_user_by_wa_id

logger = logging.getLogger(__name__)


async def identify_user(state: dict, config: RunnableConfig, *, store: BaseStore) -> Command:
    """Look up the user by WhatsApp ID. Create a new user if not found.

    Also updates last_active_at (for 24h window tracking) and flushes
    any pending notifications queued while the user was offline.
    """
    wa_id = state["wa_id"]
    conn = config["configurable"]["conn"]

    user = await get_user_by_wa_id(conn, wa_id)

    if user is None:
        user = await create_user(conn, wa_id)
        logger.info("New user created: %s", wa_id)

    user_id = str(user["id"])

    # Update 24h window timestamp
    await update_last_active(conn, user_id)

    # Flush any queued notifications (free — user just messaged us)
    await flush_pending_notifications(conn, user_id, wa_id)

    return Command(
        goto="classify_intent",
        update={
            "user_id": user_id,
            "user_role": user.get("role"),
        },
    )
