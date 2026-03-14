"""Tests for Pydantic models."""

from datetime import date

from src.models.listing import ExtractedListing
from src.models.search import SeekingPreferences


class TestExtractedListing:
    def test_complete_listing(self):
        listing = ExtractedListing(
            city="Berlin",
            neighborhood="Kreuzberg",
            rent_amount=1200,
            rooms=2.0,
            available_from=date(2026, 4, 1),
            listing_type="sublet",
            summary="Cozy 2BR in Kreuzberg",
        )
        assert listing.is_complete
        assert listing.missing_required_fields() == []

    def test_incomplete_listing_missing_rent(self):
        listing = ExtractedListing(
            city="Berlin",
            rooms=2.0,
            available_from=date(2026, 4, 1),
            summary="A place in Berlin",
        )
        assert not listing.is_complete
        assert "rent_amount" in listing.missing_required_fields()

    def test_incomplete_listing_missing_all_required(self):
        listing = ExtractedListing(summary="Some place")
        missing = listing.missing_required_fields()
        assert "rent_amount" in missing
        assert "rooms" in missing
        assert "available_from" in missing
        assert len(missing) == 3

    def test_defaults(self):
        listing = ExtractedListing(summary="Test")
        assert listing.city == "Berlin"
        assert listing.amenities == []
        assert listing.neighborhood is None


class TestSeekingPreferences:
    def test_full_preferences(self):
        prefs = SeekingPreferences(
            city="Berlin",
            neighborhoods=["Kreuzberg", "Neukölln"],
            max_rent=1500,
            min_rooms=2.0,
            move_in_date=date(2026, 4, 1),
            duration_months=6,
            preferences=["furnished", "pets_ok"],
            summary="Looking for a furnished 2BR in Kreuzberg or Neukölln",
        )
        assert prefs.max_rent == 1500
        assert len(prefs.neighborhoods) == 2

    def test_defaults(self):
        prefs = SeekingPreferences(summary="Any place in Berlin")
        assert prefs.city == "Berlin"
        assert prefs.neighborhoods == []
        assert prefs.max_rent is None
