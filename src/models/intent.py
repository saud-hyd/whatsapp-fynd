from typing import Literal

from pydantic import BaseModel, Field


class ClassifiedIntent(BaseModel):
    """Intent classified by Gemini from user message."""

    intent: Literal[
        "onboard",
        "list_place",
        "search_place",
        "opt_in_response",
        "update_listing",
        "help",
        "unknown",
    ] = Field(description="The classified intent of the user message")
    confidence: float = Field(ge=0, le=1, description="Confidence score between 0 and 1")
