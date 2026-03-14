"""Tests for FastAPI webhook endpoints."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a test client with _process_message mocked out (no DB/graph needed)."""
    from src.main import app

    with patch("src.main._process_message", new_callable=AsyncMock):
        yield TestClient(app)


class TestWebhookVerification:
    def test_valid_verification(self, client):
        resp = client.get(
            "/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.challenge": "12345",
                "hub.verify_token": "test_verify_token",
            },
        )
        assert resp.status_code == 200
        assert resp.text == "12345"

    def test_invalid_token(self, client):
        resp = client.get(
            "/webhook",
            params={
                "hub.mode": "subscribe",
                "hub.challenge": "12345",
                "hub.verify_token": "wrong_token",
            },
        )
        assert resp.status_code == 403

    def test_invalid_mode(self, client):
        resp = client.get(
            "/webhook",
            params={
                "hub.mode": "unsubscribe",
                "hub.challenge": "12345",
                "hub.verify_token": "test_verify_token",
            },
        )
        assert resp.status_code == 403


class TestWebhookPost:
    def test_handles_text_message(self, client):
        payload = {
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
        resp = client.post("/webhook", json=payload)
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_handles_empty_payload(self, client):
        resp = client.post("/webhook", json={})
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_handles_status_update(self, client):
        payload = {"entry": [{"changes": [{"value": {"statuses": [{"status": "read"}]}}]}]}
        resp = client.post("/webhook", json=payload)
        assert resp.status_code == 200

    def test_health_check(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "healthy"}
