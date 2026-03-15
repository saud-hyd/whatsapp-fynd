"""Search and match node — extract preferences, find matches, present one at a time."""

import logging

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from src.graph.prompts import MATCH_REASON, SEARCH_EXTRACTION
from src.models.search import SeekingPreferences
from src.services.embeddings import generate_embedding
from src.services.gemini import get_llm
from src.services.supabase import find_matches, update_user_role

logger = logging.getLogger(__name__)


async def search_and_match(state: dict, config: RunnableConfig) -> Command:
    """Extract seeker preferences, search for matches, present one at a time."""
    llm = get_llm()
    conn = config["configurable"]["conn"]

    # Extract preferences from conversation
    extractor = llm.with_structured_output(SeekingPreferences)
    messages = [SystemMessage(content=SEARCH_EXTRACTION), *state["messages"]]
    prefs = await extractor.ainvoke(messages)

    logger.info("Extracted preferences: %s", prefs.model_dump())

    # If city is missing, ask via follow-up (route to ask_city node)
    if not prefs.city:
        return Command(
            goto="ask_search_info",
            update={
                "extracted_preferences": prefs.model_dump(),
                "response_type": "text",
                "response_payload": {"body": "Which city are you looking in?"},
            },
        )

    # If seeker intro is missing, ask for it
    if not prefs.seeker_intro:
        return Command(
            goto="ask_search_info",
            update={
                "extracted_preferences": prefs.model_dump(),
                "response_type": "text",
                "response_payload": {
                    "body": (
                        "Before I search, could you tell me a bit about yourself? "
                        "Just a quick intro — what you do, your lifestyle. "
                        "It helps listers get to know who's interested."
                    ),
                },
            },
        )

    # Update user role
    if not state.get("user_role"):
        await update_user_role(conn, state["user_id"], "seeker")

    # Generate embedding for semantic search
    embedding = await generate_embedding(prefs.summary, "RETRIEVAL_QUERY")

    # Search for matches
    matches = await find_matches(
        conn,
        embedding,
        prefs.city,
        max_rent=prefs.max_rent,
        min_rooms=prefs.min_rooms,
        limit=3,
    )

    if not matches:
        return Command(
            goto="respond",
            update={
                "extracted_preferences": prefs.model_dump(),
                "user_role": state.get("user_role") or "seeker",
                "response_type": "text",
                "response_payload": {
                    "body": (
                        "No matches yet for your search — but I've saved your preferences. "
                        "I'll let you know as soon as something comes up!\n\n"
                        f"{prefs.format_summary()}"
                    ),
                },
            },
        )

    # Generate match reasons
    match_results = []
    for m in matches:
        reason_prompt = MATCH_REASON.format(
            listing=m.get("summary", ""),
            preferences=prefs.summary,
        )
        reason_resp = await llm.ainvoke([HumanMessage(content=reason_prompt)])
        m["match_reason"] = reason_resp.content
        match_results.append(m)

    # Present the first match
    return _present_match(state, prefs, match_results, 0)


def _present_match(
    state: dict,
    prefs: SeekingPreferences,
    match_results: list[dict],
    index: int,
) -> Command:
    """Build a Command to present a single match with action buttons."""
    match = match_results[index]
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
    lines.append(f"\nMatch {index + 1} of {total}")

    body = "\n".join(lines)

    buttons = [{"id": f"match_interested_{index}", "title": "Interested"}]
    if index + 1 < total:
        buttons.append({"id": f"match_next_{index}", "title": "Next"})
    buttons.append({"id": "match_skip_all", "title": "Skip all"})

    return Command(
        goto="respond",
        update={
            "extracted_preferences": prefs.model_dump(),
            "match_results": [_serialize_match(m) for m in match_results],
            "current_match_index": index,
            "user_role": state.get("user_role") or "seeker",
            "response_type": "interactive_buttons",
            "response_payload": {"body": body, "buttons": buttons},
        },
    )


def _serialize_match(match: dict) -> dict:
    """Make match dict JSON-serializable for state storage."""
    result = {}
    for k, v in match.items():
        if hasattr(v, "isoformat"):
            result[k] = v.isoformat()
        elif isinstance(v, list):
            result[k] = [str(i) for i in v]
        else:
            result[k] = v
    return result
