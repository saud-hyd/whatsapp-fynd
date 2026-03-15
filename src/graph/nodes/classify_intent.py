"""Classify intent node — Gemini structured output to route the conversation."""

import logging

from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from src.graph.prompts import INTENT_CLASSIFICATION
from src.models.intent import ClassifiedIntent
from src.services.gemini import get_llm

logger = logging.getLogger(__name__)


async def classify_intent(state: dict, config: RunnableConfig) -> Command:
    """Classify the user's intent and route to the appropriate node."""
    llm = get_llm()
    classifier = llm.with_structured_output(ClassifiedIntent)

    messages = [SystemMessage(content=INTENT_CLASSIFICATION), *state["messages"]]
    result = await classifier.ainvoke(messages)

    logger.info("Intent: %s (confidence: %.2f)", result.intent, result.confidence)

    # Route based on intent — smart skip to action even for new users
    intent = result.intent
    route_map = {
        "list_place": "extract_listing",
        "search_place": "search_and_match",
        "opt_in_response": "handle_opt_in",
        "update_listing": "extract_listing",
        "onboard": "onboard_user",
        "help": "respond_help",
        "unknown": "respond_unknown",
    }

    goto = route_map.get(intent, "onboard_user")

    # For list/search intents from new users (no role yet), still go to action
    # The role will be inferred from their action
    return Command(
        goto=goto,
        update={"intent": intent},
    )
