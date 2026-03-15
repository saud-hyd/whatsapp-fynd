"""Tests for WhatsApp message parsing and security utilities."""

import hashlib
import hmac

from src.services.whatsapp import extract_message, parse_message_content, verify_webhook_signature


class TestExtractMessage:
    def test_extracts_text_message(self):
        body = {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [
                                    {
                                        "from": "4917612345678",
                                        "type": "text",
                                        "text": {"body": "Hello"},
                                    }
                                ]
                            }
                        }
                    ]
                }
            ]
        }
        msg = extract_message(body)
        assert msg is not None
        assert msg["from"] == "4917612345678"
        assert msg["type"] == "text"

    def test_returns_none_for_empty_body(self):
        assert extract_message({}) is None

    def test_returns_none_for_no_messages(self):
        body = {"entry": [{"changes": [{"value": {}}]}]}
        assert extract_message(body) is None

    def test_returns_none_for_status_update(self):
        body = {"entry": [{"changes": [{"value": {"statuses": [{"status": "read"}]}}]}]}
        assert extract_message(body) is None


class TestParseMessageContent:
    def test_parses_text_message(self):
        message = {"type": "text", "text": {"body": "Looking for a 2BR in Kreuzberg"}}
        text, msg_type = parse_message_content(message)
        assert text == "Looking for a 2BR in Kreuzberg"
        assert msg_type == "text"

    def test_parses_button_reply(self):
        message = {
            "type": "interactive",
            "interactive": {
                "type": "button_reply",
                "button_reply": {"id": "role_seeker", "title": "I need a place"},
            },
        }
        text, msg_type = parse_message_content(message)
        assert text == "role_seeker"
        assert msg_type == "button_reply"

    def test_parses_list_reply(self):
        message = {
            "type": "interactive",
            "interactive": {
                "type": "list_reply",
                "list_reply": {"id": "match_abc123", "title": "2BR - Kreuzberg"},
            },
        }
        text, msg_type = parse_message_content(message)
        assert text == "match_abc123"
        assert msg_type == "list_reply"

    def test_returns_unknown_for_unsupported_type(self):
        message = {"type": "image"}
        text, msg_type = parse_message_content(message)
        assert text == ""
        assert msg_type == "unknown"


class TestWebhookSignatureVerification:
    def test_valid_signature(self):
        payload = b'{"test": "data"}'
        secret = "my_app_secret"
        expected_hash = hmac.HMAC(secret.encode(), payload, hashlib.sha256).hexdigest()
        signature = f"sha256={expected_hash}"

        assert verify_webhook_signature(payload, signature, secret) is True

    def test_invalid_signature(self):
        payload = b'{"test": "data"}'
        assert verify_webhook_signature(payload, "sha256=invalid", "secret") is False

    def test_empty_signature(self):
        payload = b'{"test": "data"}'
        assert verify_webhook_signature(payload, "", "secret") is False

    def test_tampered_payload(self):
        payload = b'{"test": "data"}'
        secret = "my_app_secret"
        expected_hash = hmac.HMAC(secret.encode(), payload, hashlib.sha256).hexdigest()
        signature = f"sha256={expected_hash}"

        tampered = b'{"test": "hacked"}'
        assert verify_webhook_signature(tampered, signature, secret) is False
