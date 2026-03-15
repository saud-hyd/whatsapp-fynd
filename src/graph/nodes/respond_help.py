"""Help response node — sends help text explaining how the bot works."""

from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from src.graph.prompts import HELP_MESSAGE


async def respond_help(state: dict, config: RunnableConfig) -> Command:
    """Send help information."""
    return Command(
        goto="respond",
        update={
            "response_type": "text",
            "response_payload": {"body": HELP_MESSAGE},
        },
    )
