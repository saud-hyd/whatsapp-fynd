from datetime import date

from pydantic import BaseModel, Field


class SeekingPreferences(BaseModel):
    """Structured data extracted from a seeker's free-text message."""

    city: str = Field(default="Berlin")
    neighborhoods: list[str] = Field(default_factory=list)
    max_rent: int | None = None
    min_rooms: float | None = None
    move_in_date: date | None = None
    duration_months: int | None = None
    preferences: list[str] = Field(default_factory=list)
    summary: str = Field(description="Clean summary of what they're looking for")
