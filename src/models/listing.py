from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class ExtractedListing(BaseModel):
    """Structured data extracted from a lister's free-text message."""

    city: str = Field(default="Berlin")
    neighborhood: str | None = None
    rent_amount: int | None = None
    rooms: float | None = None
    available_from: date | None = None
    available_to: date | None = None
    listing_type: Literal["sublet", "rent", "wg_room"] | None = None
    amenities: list[str] = Field(default_factory=list)
    summary: str = Field(description="Clean 2-3 sentence summary")

    def missing_required_fields(self) -> list[str]:
        """Return list of required fields that are missing."""
        missing = []
        if self.rent_amount is None:
            missing.append("rent_amount")
        if self.rooms is None:
            missing.append("rooms")
        if self.available_from is None:
            missing.append("available_from")
        return missing

    @property
    def is_complete(self) -> bool:
        """Check if all required fields are present."""
        return len(self.missing_required_fields()) == 0
