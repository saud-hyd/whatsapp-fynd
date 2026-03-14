from datetime import date

from pydantic import BaseModel, Field


class SeekingPreferences(BaseModel):
    """Structured data extracted from a seeker's free-text message."""

    city: str | None = None
    neighborhoods: list[str] = Field(default_factory=list)
    max_rent: int | None = None
    min_rooms: float | None = None
    move_in_date: date | None = None
    duration_months: int | None = None
    preferences: list[str] = Field(default_factory=list)
    seeker_intro: str | None = Field(
        default=None,
        description="Short intro about the seeker: who they are, lifestyle, what they're like",
    )
    summary: str = Field(description="Clean summary of what they're looking for")

    def missing_required_fields(self) -> list[str]:
        """Return list of required fields that are missing."""
        missing = []
        if self.city is None:
            missing.append("city")
        return missing

    def format_summary(self) -> str:
        """Format preferences for display."""
        lines = [f"_{self.summary}_", ""]
        if self.city:
            lines.append(f"City: {self.city}")
        if self.neighborhoods:
            lines.append(f"Areas: {', '.join(self.neighborhoods)}")
        if self.max_rent is not None:
            lines.append(f"Budget: up to {self.max_rent} EUR/month")
        if self.min_rooms is not None:
            lines.append(f"Min rooms: {self.min_rooms}")
        if self.move_in_date:
            lines.append(f"Move-in: {self.move_in_date}")
        if self.duration_months:
            lines.append(f"Duration: {self.duration_months} months")
        if self.seeker_intro:
            lines.append(f"\nAbout me: {self.seeker_intro}")
        return "\n".join(lines)
