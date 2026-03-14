"""Shared test fixtures."""

import pytest


@pytest.fixture(autouse=True)
def _set_env(monkeypatch):
    """Set required environment variables for all tests."""
    from src.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("WA_VERIFY_TOKEN", "test_verify_token")
    monkeypatch.setenv("WA_ACCESS_TOKEN", "test_access_token")
    monkeypatch.setenv("WA_PHONE_NUMBER_ID", "123456789")
    monkeypatch.setenv("GOOGLE_API_KEY", "test_google_key")
    monkeypatch.setenv("SUPABASE_URL", "https://test.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "test_anon_key")
    monkeypatch.setenv("SUPABASE_SERVICE_KEY", "test_service_key")
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/test")
