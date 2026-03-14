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
        assert "city" in missing
        assert "rent_amount" in missing
        assert "rooms" in missing
        assert "available_from" in missing
        assert len(missing) == 4

    def test_no_city_default(self):
        listing = ExtractedListing(summary="Test")
        assert listing.city is None
        assert listing.amenities == []
        assert listing.neighborhood is None

    def test_format_confirmation(self):
        listing = ExtractedListing(
            city="Munich",
            neighborhood="Schwabing",
            rent_amount=1500,
            rooms=3.0,
            available_from=date(2026, 5, 1),
            listing_type="rent",
            amenities=["furnished", "balcony"],
            summary="Spacious 3BR in Schwabing with balcony",
        )
        text = listing.format_confirmation()
        assert "Schwabing, Munich" in text
        assert "1500 EUR/month" in text
        assert "3.0" in text
        assert "furnished, balcony" in text

    def test_city_in_required_fields(self):
        listing = ExtractedListing(
            rent_amount=1000, rooms=2.0, available_from=date(2026, 4, 1), summary="Test"
        )
        assert not listing.is_complete
        assert "city" in listing.missing_required_fields()


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
            seeker_intro="Grad student, non-smoker, work from home",
            summary="Looking for a furnished 2BR in Kreuzberg or Neukölln",
        )
        assert prefs.max_rent == 1500
        assert len(prefs.neighborhoods) == 2
        assert prefs.seeker_intro == "Grad student, non-smoker, work from home"

    def test_no_city_default(self):
        prefs = SeekingPreferences(summary="Any place")
        assert prefs.city is None
        assert prefs.neighborhoods == []
        assert prefs.max_rent is None
        assert prefs.seeker_intro is None

    def test_missing_city_detected(self):
        prefs = SeekingPreferences(summary="Looking for a place")
        assert "city" in prefs.missing_required_fields()

    def test_format_summary(self):
        prefs = SeekingPreferences(
            city="Berlin",
            max_rent=1200,
            min_rooms=2.0,
            seeker_intro="Quiet freelancer",
            summary="Looking for a 2BR under 1200",
        )
        text = prefs.format_summary()
        assert "Berlin" in text
        assert "1200" in text
        assert "Quiet freelancer" in text
