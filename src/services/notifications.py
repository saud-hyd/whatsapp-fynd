"""Notification service — smart delivery using 24h window + queue fallback."""

import json
import logging
from datetime import UTC, datetime

from src.services.whatsapp import send_buttons, send_text

logger = logging.getLogger(__name__)

# 24 hours in seconds
WINDOW_SECONDS = 24 * 3600


async def deliver_or_queue(
    conn,
    target_user_id: str,
    target_wa_id: str,
    notification_type: str,
    payload: dict,
) -> bool:
    """Send notification if user is in 24h window, otherwise queue.

    Returns True if sent immediately, False if queued.
    """
    if await _is_within_window(conn, target_user_id):
        await _send_notification(target_wa_id, notification_type, payload)
        return True

    await _queue_notification(conn, target_user_id, notification_type, payload)
    logger.info(
        "Queued %s notification for user %s (outside 24h window)",
        notification_type,
        target_user_id,
    )
    return False


async def flush_pending_notifications(conn, user_id: str, wa_id: str) -> int:
    """Send all queued notifications for a user and delete them.

    Called from identify_user when user messages the bot (free window is open).
    Returns the number of notifications sent.
    """
    rows = await conn.fetch(
        """DELETE FROM pending_notifications
           WHERE user_id = $1::uuid
           RETURNING notification_type, payload""",
        user_id,
    )

    sent = 0
    for row in rows:
        try:
            raw = row["payload"]
            payload = json.loads(raw) if isinstance(raw, str) else raw
            await _send_notification(wa_id, row["notification_type"], payload)
            sent += 1
        except Exception:
            logger.exception(
                "Failed to send queued %s notification to %s",
                row["notification_type"],
                wa_id,
            )

    if sent:
        logger.info("Flushed %d pending notifications for user %s", sent, user_id)

    return sent


async def _is_within_window(conn, user_id: str) -> bool:
    """Check if user's last activity is within the 24h free window."""
    row = await conn.fetchrow(
        "SELECT last_active_at FROM users WHERE id = $1::uuid",
        user_id,
    )
    if not row or not row["last_active_at"]:
        return False

    elapsed = (datetime.now(UTC) - row["last_active_at"]).total_seconds()
    return elapsed < WINDOW_SECONDS


async def update_last_active(conn, user_id: str) -> None:
    """Update user's last_active_at timestamp."""
    await conn.execute(
        "UPDATE users SET last_active_at = now() WHERE id = $1::uuid",
        user_id,
    )


async def _queue_notification(
    conn,
    user_id: str,
    notification_type: str,
    payload: dict,
) -> None:
    """Insert a notification into the pending queue."""
    await conn.execute(
        """INSERT INTO pending_notifications (user_id, notification_type, payload)
           VALUES ($1::uuid, $2, $3::jsonb)""",
        user_id,
        notification_type,
        json.dumps(payload),
    )


async def _send_notification(wa_id: str, notification_type: str, payload: dict) -> None:
    """Send a notification via WhatsApp based on its type."""
    if notification_type == "match_interest":
        # Lister gets notified that a seeker is interested
        await send_buttons(
            wa_id,
            payload["body"],
            payload["buttons"],
        )
    elif notification_type == "mutual_match":
        # Contact sharing after mutual acceptance
        await send_text(wa_id, payload["body"])
    else:
        # Fallback — send as text
        await send_text(wa_id, payload.get("body", "You have a notification from Fynd!"))
