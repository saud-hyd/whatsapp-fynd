"""Unknown intent response — politely redirect the user."""

from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

REDIRECT_MESSAGE = (
    "I'm Fynd — I help connect people looking for a place with those who have one! "
    "Tell me about a place you have available, or describe what you're looking for."
)


async def respond_unknown(state: dict, config: RunnableConfig) -> Command:
    """Redirect user when intent is unclear or off-topic."""
    return Command(
        goto="respond",
        update={
            "response_type": "text",
            "response_payload": {"body": REDIRECT_MESSAGE},
        },
    )
