"""Tests for the notification service — deliver-or-queue logic."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def mock_conn():
    """Create a mock async database connection."""
    conn = AsyncMock()
    return conn


class TestDeliverOrQueue:
    @pytest.mark.asyncio
    async def test_delivers_when_within_window(self, mock_conn):
        """Should send immediately if user's last_active_at is within 24h."""
        from src.services.notifications import deliver_or_queue

        # User was active 1 hour ago
        mock_conn.fetchrow.return_value = {
            "last_active_at": datetime.now(UTC) - timedelta(hours=1),
        }

        with patch("src.services.notifications.send_buttons", new_callable=AsyncMock) as mock_send:
            result = await deliver_or_queue(
                mock_conn,
                "user-123",
                "491234567",
                "match_interest",
                {"body": "Someone is interested!", "buttons": [{"id": "x", "title": "Accept"}]},
            )

        assert result is True
        mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_queues_when_outside_window(self, mock_conn):
        """Should queue if user's last_active_at is older than 24h."""
        from src.services.notifications import deliver_or_queue

        # User was active 25 hours ago
        mock_conn.fetchrow.return_value = {
            "last_active_at": datetime.now(UTC) - timedelta(hours=25),
        }

        result = await deliver_or_queue(
            mock_conn,
            "user-123",
            "491234567",
            "match_interest",
            {"body": "Someone is interested!", "buttons": [{"id": "x", "title": "Accept"}]},
        )

        assert result is False
        # Should have queued via INSERT
        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args
        assert "INSERT INTO pending_notifications" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_queues_when_never_active(self, mock_conn):
        """Should queue if user has no last_active_at."""
        from src.services.notifications import deliver_or_queue

        mock_conn.fetchrow.return_value = {"last_active_at": None}

        result = await deliver_or_queue(
            mock_conn, "user-123", "491234567", "match_interest", {"body": "Hi"}
        )

        assert result is False
        mock_conn.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_queues_when_user_not_found(self, mock_conn):
        """Should queue if user record not found."""
        from src.services.notifications import deliver_or_queue

        mock_conn.fetchrow.return_value = None

        result = await deliver_or_queue(
            mock_conn, "user-123", "491234567", "mutual_match", {"body": "Match!"}
        )

        assert result is False


class TestFlushPendingNotifications:
    @pytest.mark.asyncio
    async def test_flushes_and_sends(self, mock_conn):
        """Should send all pending notifications and return count."""
        from src.services.notifications import flush_pending_notifications

        mock_conn.fetch.return_value = [
            {
                "notification_type": "match_interest",
                "payload": '{"body": "Notification 1", "buttons": [{"id": "a", "title": "OK"}]}',
            },
            {
                "notification_type": "mutual_match",
                "payload": '{"body": "Notification 2"}',
            },
        ]

        with (
            patch("src.services.notifications.send_buttons", new_callable=AsyncMock),
            patch("src.services.notifications.send_text", new_callable=AsyncMock),
        ):
            count = await flush_pending_notifications(mock_conn, "user-123", "491234567")

        assert count == 2
        # Should have DELETE'd from pending_notifications
        call_args = mock_conn.fetch.call_args
        assert "DELETE FROM pending_notifications" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_returns_zero_when_no_pending(self, mock_conn):
        """Should return 0 if no pending notifications."""
        from src.services.notifications import flush_pending_notifications

        mock_conn.fetch.return_value = []

        count = await flush_pending_notifications(mock_conn, "user-123", "491234567")
        assert count == 0

    @pytest.mark.asyncio
    async def test_handles_send_failure_gracefully(self, mock_conn):
        """Should continue sending other notifications if one fails."""
        from src.services.notifications import flush_pending_notifications

        mock_conn.fetch.return_value = [
            {
                "notification_type": "mutual_match",
                "payload": '{"body": "Will fail"}',
            },
            {
                "notification_type": "mutual_match",
                "payload": '{"body": "Will succeed"}',
            },
        ]

        call_count = 0

        async def mock_send_text(to, body):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Network error")

        with patch("src.services.notifications.send_text", side_effect=mock_send_text):
            count = await flush_pending_notifications(mock_conn, "user-123", "491234567")

        # Only the second one succeeded
        assert count == 1


class TestUpdateLastActive:
    @pytest.mark.asyncio
    async def test_updates_timestamp(self, mock_conn):
        """Should call UPDATE on users table."""
        from src.services.notifications import update_last_active

        await update_last_active(mock_conn, "user-123")

        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args
        assert "UPDATE users SET last_active_at" in call_args[0][0]


class TestNotificationTypes:
    @pytest.mark.asyncio
    async def test_match_interest_sends_buttons(self, mock_conn):
        """match_interest notifications should use send_buttons."""
        from src.services.notifications import deliver_or_queue

        mock_conn.fetchrow.return_value = {
            "last_active_at": datetime.now(UTC),
        }

        with patch("src.services.notifications.send_buttons", new_callable=AsyncMock) as mock_btn:
            await deliver_or_queue(
                mock_conn,
                "user-123",
                "491234567",
                "match_interest",
                {"body": "Interest!", "buttons": [{"id": "a", "title": "Accept"}]},
            )

        mock_btn.assert_called_once_with("491234567", "Interest!", [{"id": "a", "title": "Accept"}])

    @pytest.mark.asyncio
    async def test_mutual_match_sends_text(self, mock_conn):
        """mutual_match notifications should use send_text."""
        from src.services.notifications import deliver_or_queue

        mock_conn.fetchrow.return_value = {
            "last_active_at": datetime.now(UTC),
        }

        with patch("src.services.notifications.send_text", new_callable=AsyncMock) as mock_text:
            await deliver_or_queue(
                mock_conn,
                "user-123",
                "491234567",
                "mutual_match",
                {"body": "It's a match!"},
            )

        mock_text.assert_called_once_with("491234567", "It's a match!")
