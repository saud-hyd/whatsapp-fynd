from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class ExtractedListing(BaseModel):
    """Structured data extracted from a lister's free-text message."""

    city: str | None = None
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
        if self.city is None:
            missing.append("city")
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

    def format_confirmation(self) -> str:
        """Format listing for user confirmation."""
        lines = [f"_{self.summary}_", ""]
        if self.city:
            loc = self.city
            if self.neighborhood:
                loc = f"{self.neighborhood}, {self.city}"
            lines.append(f"Location: {loc}")
        if self.rent_amount is not None:
            lines.append(f"Rent: {self.rent_amount} EUR/month")
        if self.rooms is not None:
            lines.append(f"Rooms: {self.rooms}")
        if self.listing_type:
            lines.append(f"Type: {self.listing_type}")
        if self.available_from:
            avail = f"From {self.available_from}"
            if self.available_to:
                avail += f" to {self.available_to}"
            lines.append(f"Available: {avail}")
        if self.amenities:
            lines.append(f"Amenities: {', '.join(self.amenities)}")
        return "\n".join(lines)
