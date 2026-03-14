"""Handle opt-in node — process match interest, double opt-in, share contacts."""

import logging

from langgraph.types import Command

from src.services.supabase import create_match, get_match_by_id, update_match_status
from src.services.whatsapp import send_buttons, send_text

logger = logging.getLogger(__name__)


async def handle_opt_in(state: dict, config: dict) -> Command:
    """Handle match-related button responses: interested, next, accept, reject."""
    conn = config["configurable"]["conn"]
    last_message = state["messages"][-1].content if state["messages"] else ""

    # Seeker tapped "Interested" on a match
    if last_message.startswith("match_interested_"):
        return await _handle_seeker_interested(state, conn, last_message)

    # Seeker tapped "Next" to see next match
    if last_message.startswith("match_next_"):
        return _handle_next_match(state)

    # Seeker tapped "Skip all"
    if last_message == "match_skip_all":
        return Command(
            goto="respond",
            update={
                "response_type": "text",
                "response_payload": {
                    "body": (
                        "No worries! Your preferences are saved"
                        " — I'll let you know when new listings come up."
                    ),
                },
            },
        )

    # Lister responding to a match notification: accept or reject
    if last_message.startswith("opt_accept_"):
        match_id = last_message.replace("opt_accept_", "")
        return await _handle_lister_response(state, conn, match_id, "accepted")

    if last_message.startswith("opt_reject_"):
        match_id = last_message.replace("opt_reject_", "")
        return await _handle_lister_response(state, conn, match_id, "rejected")

    # Fallback
    return Command(
        goto="respond",
        update={
            "response_type": "text",
            "response_payload": {
                "body": "I didn't catch that. Could you try again?",
            },
        },
    )


async def _handle_seeker_interested(state: dict, conn, last_message: str) -> Command:
    """Seeker expressed interest in a match — create match record, notify lister."""
    index = int(last_message.replace("match_interested_", ""))
    match_results = state.get("match_results", [])

    if index >= len(match_results):
        return Command(
            goto="respond",
            update={
                "response_type": "text",
                "response_payload": {"body": "That match is no longer available."},
            },
        )

    listing = match_results[index]
    prefs = state.get("extracted_preferences", {})

    # Create match record
    match_record = await create_match(
        conn,
        listing_id=str(listing["id"]),
        seeker_id=state["user_id"],
        lister_id=str(listing["user_id"]),
        similarity=float(listing.get("similarity", 0)),
        seeker_status="accepted",
    )

    logger.info("Match created: %s", match_record["id"])

    # Notify the lister via WhatsApp
    lister_wa_id = listing.get("wa_id", listing.get("lister_wa_id", ""))
    if lister_wa_id:
        seeker_intro = prefs.get("seeker_intro", "")
        intro_text = f"\n\nAbout them: {seeker_intro}" if seeker_intro else ""

        notification_body = (
            f"Someone is interested in your listing: {listing.get('summary', 'your place')}!"
            f"{intro_text}"
            f"\n\nWould you like to connect?"
        )

        try:
            await send_buttons(
                lister_wa_id,
                notification_body,
                [
                    {"id": f"opt_accept_{match_record['id']}", "title": "Accept"},
                    {"id": f"opt_reject_{match_record['id']}", "title": "Decline"},
                ],
            )
        except Exception:
            logger.exception("Failed to notify lister %s", lister_wa_id)

    return Command(
        goto="respond",
        update={
            "response_type": "text",
            "response_payload": {
                "body": (
                    "I've let them know you're interested! "
                    "If they're up for it, I'll connect you both."
                ),
            },
        },
    )


def _handle_next_match(state: dict) -> Command:
    """Show the next match in the list."""
    match_results = state.get("match_results", [])
    current_index = state.get("current_match_index", 0)
    next_index = current_index + 1

    if next_index >= len(match_results):
        return Command(
            goto="respond",
            update={
                "response_type": "text",
                "response_payload": {
                    "body": (
                        "That's all the matches I have right now."
                        " I'll notify you when new listings come up!"
                    ),
                },
            },
        )

    match = match_results[next_index]
    total = len(match_results)

    lines = []
    if match.get("match_reason"):
        lines.append(f"_{match['match_reason']}_")
        lines.append("")
    if match.get("summary"):
        lines.append(match["summary"])
        lines.append("")
    loc = match.get("city", "")
    if match.get("neighborhood"):
        loc = f"{match['neighborhood']}, {loc}"
    if loc:
        lines.append(f"Location: {loc}")
    if match.get("rent_amount") is not None:
        lines.append(f"Rent: {match['rent_amount']} EUR/month")
    if match.get("rooms") is not None:
        lines.append(f"Rooms: {match['rooms']}")
    lines.append(f"\nMatch {next_index + 1} of {total}")

    body = "\n".join(lines)

    buttons = [{"id": f"match_interested_{next_index}", "title": "Interested"}]
    if next_index + 1 < total:
        buttons.append({"id": f"match_next_{next_index}", "title": "Next"})
    buttons.append({"id": "match_skip_all", "title": "Skip all"})

    return Command(
        goto="respond",
        update={
            "current_match_index": next_index,
            "response_type": "interactive_buttons",
            "response_payload": {"body": body, "buttons": buttons},
        },
    )


async def _handle_lister_response(state: dict, conn, match_id: str, status: str) -> Command:
    """Lister accepted or rejected a match — check for mutual acceptance."""
    await update_match_status(conn, match_id, "lister", status)

    match = await get_match_by_id(conn, match_id)
    if not match:
        return Command(
            goto="respond",
            update={
                "response_type": "text",
                "response_payload": {"body": "This match is no longer available."},
            },
        )

    if status == "rejected":
        return Command(
            goto="respond",
            update={
                "response_type": "text",
                "response_payload": {
                    "body": "Got it — I won't share your details. No worries!",
                },
            },
        )

    # Lister accepted — check if seeker also accepted (mutual match!)
    if match["seeker_status"] == "accepted" and status == "accepted":
        # Both accepted — share contact info
        seeker_wa = match["seeker_wa_id"]
        lister_wa = match["lister_wa_id"]
        seeker_name = match.get("seeker_name") or "the seeker"
        lister_name = match.get("lister_name") or "the lister"
        listing_summary = match.get("listing_summary", "the listing")

        # Notify seeker
        try:
            await send_text(
                seeker_wa,
                f"Great news! {lister_name} wants to connect with you about: {listing_summary}\n\n"
                f"Their WhatsApp: wa.me/{lister_wa}\n\n"
                "Go ahead and reach out!",
            )
        except Exception:
            logger.exception("Failed to notify seeker %s", seeker_wa)

        # Tell lister
        return Command(
            goto="respond",
            update={
                "response_type": "text",
                "response_payload": {
                    "body": (
                        f"It's a match! {seeker_name} is also interested.\n\n"
                        f"Their WhatsApp: wa.me/{seeker_wa}\n\n"
                        "Feel free to reach out to each other!"
                    ),
                },
            },
        )

    # Seeker hasn't responded yet
    return Command(
        goto="respond",
        update={
            "response_type": "text",
            "response_payload": {
                "body": "Thanks for accepting! I'll let you know once they confirm too.",
            },
        },
    )
