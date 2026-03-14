"""Unknown intent response — politely redirect the user."""

from langgraph.types import Command

REDIRECT_MESSAGE = (
    "I'm here to help you find or list a place in Berlin! "
    "Tell me about a place you have available, or describe what you're looking for."
)


async def respond_unknown(state: dict, config: dict) -> Command:
    """Redirect user when intent is unclear or off-topic."""
    return Command(
        goto="respond",
        update={
            "response_type": "text",
            "response_payload": {"body": REDIRECT_MESSAGE},
        },
    )
