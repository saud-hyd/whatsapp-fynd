"""Integration tests — full webhook flow and service interactions with fake data.

Tests the complete message flow from webhook POST to WhatsApp response,
with all external services mocked but internal routing working end-to-end.
"""

import hashlib
import hmac
import json
import uuid
from datetime import UTC, date, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.models.intent import ClassifiedIntent
from src.models.listing import ExtractedListing
from src.models.search import SeekingPreferences
from src.services.supabase import _format_vector

# -- Fake data fixtures --

LISTER_WA_ID = "4917600000001"
SEEKER_WA_ID = "4917600000002"
LISTER_USER_ID = str(uuid.uuid4())
SEEKER_USER_ID = str(uuid.uuid4())
LISTING_ID = str(uuid.uuid4())
MATCH_ID = str(uuid.uuid4())

FAKE_LISTER = {
    "id": LISTER_USER_ID,
    "wa_id": LISTER_WA_ID,
    "name": "Alice",
    "role": "lister",
    "city": "Berlin",
    "last_active_at": datetime.now(UTC),
}

FAKE_SEEKER = {
    "id": SEEKER_USER_ID,
    "wa_id": SEEKER_WA_ID,
    "name": "Bob",
    "role": "seeker",
    "city": "Berlin",
    "last_active_at": datetime.now(UTC),
}

FAKE_LISTING = {
    "id": LISTING_ID,
    "user_id": LISTER_USER_ID,
    "raw_text": "2BR in Kreuzberg, 800/month, from April",
    "city": "Berlin",
    "neighborhood": "Kreuzberg",
    "rent_amount": 800,
    "rooms": 2.0,
    "available_from": date(2026, 4, 1),
    "available_to": None,
    "listing_type": "sublet",
    "amenities": ["furnished", "balcony"],
    "summary": "Sunny 2BR sublet in Kreuzberg with balcony, available from April.",
    "similarity": 0.89,
    "wa_id": LISTER_WA_ID,
    "lister_name": "Alice",
    "is_active": True,
}

FAKE_MATCH = {
    "id": MATCH_ID,
    "listing_id": LISTING_ID,
    "seeker_id": SEEKER_USER_ID,
    "lister_id": LISTER_USER_ID,
    "similarity": 0.89,
    "seeker_status": "accepted",
    "lister_status": "pending",
    "seeker_wa_id": SEEKER_WA_ID,
    "lister_wa_id": LISTER_WA_ID,
    "seeker_name": "Bob",
    "lister_name": "Alice",
    "listing_summary": "Sunny 2BR in Kreuzberg",
}

FAKE_EMBEDDING = [0.1] * 768


def make_webhook_payload(from_id: str, text: str, msg_id: str | None = None) -> dict:
    """Build a WhatsApp webhook payload for a text message."""
    return {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "id": msg_id or f"wamid.{uuid.uuid4().hex[:20]}",
                                    "from": from_id,
                                    "type": "text",
                                    "text": {"body": text},
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }


def make_button_payload(from_id: str, button_id: str, title: str) -> dict:
    """Build a WhatsApp webhook payload for a button reply."""
    return {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "id": f"wamid.{uuid.uuid4().hex[:20]}",
                                    "from": from_id,
                                    "type": "interactive",
                                    "interactive": {
                                        "type": "button_reply",
                                        "button_reply": {
                                            "id": button_id,
                                            "title": title,
                                        },
                                    },
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }


# -- Webhook integration tests --


@pytest.fixture
def webhook_client():
    """Create a test client with _process_message mocked (no DB/graph needed).

    Uses TestClient without context manager to avoid triggering lifespan
    (which tries to connect to the real database).
    """
    from src.main import _processed_messages, app

    _processed_messages.clear()
    with patch("src.main._process_message", new_callable=AsyncMock):
        yield TestClient(app)
    _processed_messages.clear()


class TestWebhookSignatureFlow:
    def test_valid_signature_passes(self, webhook_client):
        """Webhook with empty app_secret should accept all requests."""
        payload = make_webhook_payload(LISTER_WA_ID, "Hello")
        resp = webhook_client.post("/webhook", json=payload)
        assert resp.status_code == 200

    def test_signature_verification_logic(self):
        """HMAC verification function should reject invalid signatures."""
        from src.services.whatsapp import verify_webhook_signature

        payload = b'{"test": "data"}'
        secret = "real_secret"

        # Valid signature
        valid_hash = hmac.HMAC(secret.encode(), payload, hashlib.sha256).hexdigest()
        assert verify_webhook_signature(payload, f"sha256={valid_hash}", secret) is True

        # Invalid signature
        assert verify_webhook_signature(payload, "sha256=invalid", secret) is False


class TestWebhookDeduplication:
    def test_duplicate_message_ignored(self, webhook_client):
        """Same message ID should only be processed once."""
        from src.main import _processed_messages

        payload = make_webhook_payload(LISTER_WA_ID, "Hello", msg_id="wamid.dup123")

        webhook_client.post("/webhook", json=payload)
        webhook_client.post("/webhook", json=payload)

        assert "wamid.dup123" in _processed_messages


class TestWebhookMessageParsing:
    def test_text_message_parsed(self, webhook_client):
        """Text messages should be extracted and passed to _process_message."""
        payload = make_webhook_payload(LISTER_WA_ID, "I have a 2BR in Berlin")
        resp = webhook_client.post("/webhook", json=payload)
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_button_reply_parsed(self, webhook_client):
        """Button replies should be extracted correctly."""
        payload = make_button_payload(LISTER_WA_ID, "action_list", "I have a place")
        resp = webhook_client.post("/webhook", json=payload)
        assert resp.status_code == 200

    def test_status_update_ignored(self):
        """Status updates (read receipts) should not trigger processing."""
        from src.main import app

        with patch("src.main._process_message", new_callable=AsyncMock) as mock_process:
            client = TestClient(app)
            payload = {"entry": [{"changes": [{"value": {"statuses": [{"status": "read"}]}}]}]}
            resp = client.post("/webhook", json=payload)
            assert resp.status_code == 200
            mock_process.assert_not_called()


# -- Data format tests --


class TestDataFormats:
    def test_vector_format(self):
        """Embedding vectors should be formatted correctly for pgvector."""
        vec = [0.1, 0.2, 0.3]
        result = _format_vector(vec)
        assert result == "[0.1,0.2,0.3]"
        # No spaces after commas
        assert " " not in result

    def test_vector_format_none(self):
        assert _format_vector(None) is None

    def test_vector_format_string_passthrough(self):
        assert _format_vector("[0.1,0.2]") == "[0.1,0.2]"

    def test_listing_confirmation_format(self):
        """Listing confirmation should contain key fields for button detection."""
        listing = ExtractedListing(
            city="Berlin",
            neighborhood="Kreuzberg",
            rent_amount=800,
            rooms=2.0,
            available_from=date(2026, 4, 1),
            listing_type="sublet",
            amenities=["furnished"],
            summary="Sunny 2BR in Kreuzberg.",
        )
        confirmation = listing.format_confirmation()
        # These are used by _send_interrupt_message to detect confirmation
        assert "Rent:" in confirmation
        assert "Rooms:" in confirmation
        assert "800" in confirmation
        assert "Kreuzberg" in confirmation

    def test_seeker_preferences_format(self):
        """Preferences summary should be readable."""
        prefs = SeekingPreferences(
            city="Munich",
            max_rent=600,
            min_rooms=1.0,
            seeker_intro="I'm a student.",
            summary="Student looking for room in Munich.",
        )
        summary = prefs.format_summary()
        assert "Munich" in summary
        assert "600" in summary
        assert "student" in summary.lower()


# -- Model validation tests with realistic data --


class TestRealisticDataValidation:
    def test_complete_listing_is_valid(self):
        """A realistic complete listing should pass validation."""
        listing = ExtractedListing(
            city="Berlin",
            neighborhood="Prenzlauer Berg",
            rent_amount=950,
            rooms=3.0,
            available_from=date(2026, 5, 1),
            available_to=date(2026, 9, 30),
            listing_type="sublet",
            amenities=["furnished", "balcony", "washing_machine"],
            summary="Spacious 3-room flat in Prenzlauer Berg, fully furnished with balcony.",
        )
        assert listing.is_complete
        assert listing.missing_required_fields() == []

    def test_minimal_listing_missing_fields(self):
        """A listing with only city should report missing fields."""
        listing = ExtractedListing(
            city="Hamburg",
            summary="A place in Hamburg.",
        )
        missing = listing.missing_required_fields()
        assert "rent_amount" in missing
        assert "rooms" in missing
        assert "available_from" in missing
        assert "city" not in missing

    def test_intent_classification_values(self):
        """All expected intents should be valid."""
        for intent in [
            "list_place",
            "search_place",
            "opt_in_response",
            "update_listing",
            "help",
            "onboard",
            "unknown",
        ]:
            ci = ClassifiedIntent(intent=intent, confidence=0.9)
            assert ci.intent == intent

    def test_seeking_preferences_city_required(self):
        """City should be in missing fields when not provided."""
        prefs = SeekingPreferences(
            max_rent=500,
            summary="Looking for something cheap.",
        )
        assert "city" in prefs.missing_required_fields()

    def test_seeking_preferences_complete(self):
        """Complete preferences should have no missing fields."""
        prefs = SeekingPreferences(
            city="Berlin",
            neighborhoods=["Kreuzberg", "Neukölln"],
            max_rent=700,
            min_rooms=1.5,
            move_in_date=date(2026, 4, 15),
            duration_months=6,
            preferences=["furnished", "quiet"],
            seeker_intro="I'm a freelance designer, work from home, non-smoker.",
            summary="Freelance designer looking for furnished 1.5+ room in Kreuzberg or Neukölln.",
        )
        assert prefs.missing_required_fields() == []


# -- Interrupt message detection test --


class TestInterruptMessageDetection:
    @pytest.mark.asyncio
    async def test_listing_confirmation_gets_buttons(self):
        """_send_interrupt_message should detect listing confirmations and send buttons."""
        from src.main import _send_interrupt_message

        # A listing confirmation always has "Rent:" and "Rooms:"
        value = (
            "_Sunny 2BR in Kreuzberg._\n\n"
            "Location: Kreuzberg, Berlin\n"
            "Rent: 800 EUR/month\n"
            "Rooms: 2.0\n"
            "Type: sublet\n"
            "Available: From 2026-04-01"
        )

        with patch("src.main.send_buttons", new_callable=AsyncMock) as mock_btn:
            await _send_interrupt_message(LISTER_WA_ID, value)

        mock_btn.assert_called_once()
        args = mock_btn.call_args
        assert args[0][0] == LISTER_WA_ID
        buttons = args[0][2]
        assert any(b["id"] == "action_confirm" for b in buttons)
        assert any(b["id"] == "action_edit" for b in buttons)

    @pytest.mark.asyncio
    async def test_plain_question_gets_text(self):
        """A follow-up question should be sent as plain text."""
        from src.main import _send_interrupt_message

        value = "What's the monthly rent?"

        with patch("src.main.send_text", new_callable=AsyncMock) as mock_text:
            await _send_interrupt_message(LISTER_WA_ID, value)

        mock_text.assert_called_once_with(LISTER_WA_ID, "What's the monthly rent?")


# -- Notification flow with fake users --


class TestNotificationFlowWithFakeData:
    @pytest.mark.asyncio
    async def test_lister_in_window_gets_immediate_notification(self):
        """Lister active 1 hour ago should get notification immediately."""
        from src.services.notifications import deliver_or_queue

        conn = AsyncMock()
        conn.fetchrow.return_value = {
            "last_active_at": datetime.now(UTC) - timedelta(hours=1),
        }

        payload = {
            "body": "Bob is interested in your 2BR Kreuzberg listing!",
            "buttons": [
                {"id": f"opt_accept_{MATCH_ID}", "title": "Accept"},
                {"id": f"opt_reject_{MATCH_ID}", "title": "Decline"},
            ],
        }

        with patch("src.services.notifications.send_buttons", new_callable=AsyncMock) as mock_send:
            result = await deliver_or_queue(
                conn, LISTER_USER_ID, LISTER_WA_ID, "match_interest", payload
            )

        assert result is True
        mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_lister_outside_window_gets_queued(self):
        """Lister inactive for 25 hours should have notification queued."""
        from src.services.notifications import deliver_or_queue

        conn = AsyncMock()
        conn.fetchrow.return_value = {
            "last_active_at": datetime.now(UTC) - timedelta(hours=25),
        }

        result = await deliver_or_queue(
            conn, LISTER_USER_ID, LISTER_WA_ID, "match_interest", {"body": "Interest!"}
        )

        assert result is False
        conn.execute.assert_called_once()
        insert_sql = conn.execute.call_args[0][0]
        assert "INSERT INTO pending_notifications" in insert_sql

    @pytest.mark.asyncio
    async def test_flush_sends_queued_on_checkin(self):
        """When lister messages bot, pending notifications should be flushed."""
        from src.services.notifications import flush_pending_notifications

        conn = AsyncMock()
        conn.fetch.return_value = [
            {
                "notification_type": "match_interest",
                "payload": json.dumps(
                    {
                        "body": "Bob is interested!",
                        "buttons": [{"id": "opt_accept_123", "title": "Accept"}],
                    }
                ),
            },
        ]

        with patch("src.services.notifications.send_buttons", new_callable=AsyncMock) as mock_send:
            count = await flush_pending_notifications(conn, LISTER_USER_ID, LISTER_WA_ID)

        assert count == 1
        mock_send.assert_called_once()


# -- WhatsApp message format tests --


class TestWhatsAppMessageFormats:
    @pytest.mark.asyncio
    async def test_send_text_format(self):
        """send_text should build correct WhatsApp API payload."""
        import httpx

        mock_response = MagicMock()
        mock_response.json.return_value = {"messages": [{"id": "wamid.abc"}]}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = mock_response
        mock_client.is_closed = False

        with patch("src.services.whatsapp.get_http_client", return_value=mock_client):
            from src.services.whatsapp import send_text

            await send_text("491234567", "Hello!")

        call_args = mock_client.post.call_args
        payload = call_args[1]["json"]
        assert payload["messaging_product"] == "whatsapp"
        assert payload["to"] == "491234567"
        assert payload["type"] == "text"
        assert payload["text"]["body"] == "Hello!"

    @pytest.mark.asyncio
    async def test_send_buttons_format(self):
        """send_buttons should build interactive button payload with max 3 buttons."""
        import httpx

        mock_response = MagicMock()
        mock_response.json.return_value = {"messages": [{"id": "wamid.abc"}]}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = mock_response
        mock_client.is_closed = False

        with patch("src.services.whatsapp.get_http_client", return_value=mock_client):
            from src.services.whatsapp import send_buttons

            await send_buttons(
                "491234567",
                "Choose an option:",
                [
                    {"id": "btn_1", "title": "Option 1"},
                    {"id": "btn_2", "title": "Option 2"},
                    {"id": "btn_3", "title": "Option 3"},
                    {"id": "btn_4", "title": "Should be trimmed"},
                ],
            )

        call_args = mock_client.post.call_args
        payload = call_args[1]["json"]
        assert payload["type"] == "interactive"
        assert payload["interactive"]["type"] == "button"
        buttons = payload["interactive"]["action"]["buttons"]
        # Max 3 buttons enforced
        assert len(buttons) == 3
        assert buttons[0]["reply"]["id"] == "btn_1"

    @pytest.mark.asyncio
    async def test_send_template_format(self):
        """send_template should build template payload."""
        import httpx

        mock_response = MagicMock()
        mock_response.json.return_value = {"messages": [{"id": "wamid.abc"}]}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.post.return_value = mock_response
        mock_client.is_closed = False

        with patch("src.services.whatsapp.get_http_client", return_value=mock_client):
            from src.services.whatsapp import send_template

            await send_template("491234567", "match_notification", "en")

        call_args = mock_client.post.call_args
        payload = call_args[1]["json"]
        assert payload["type"] == "template"
        assert payload["template"]["name"] == "match_notification"
        assert payload["template"]["language"]["code"] == "en"
