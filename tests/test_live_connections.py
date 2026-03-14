"""Live connection tests — verify real services with .env credentials.

Run manually: pytest tests/test_live_connections.py -v
Skipped in CI (requires real credentials).
"""

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

# Load real .env before conftest autouse fixture overrides values
_env_path = Path(__file__).resolve().parent.parent / ".env"

pytestmark = pytest.mark.skipif(
    not _env_path.exists(),
    reason="Live tests require .env with real credentials",
)


@pytest.fixture(autouse=True)
def _load_real_env(monkeypatch):
    """Override conftest's fake env vars with real .env values for live tests."""
    from src.config import get_settings

    get_settings.cache_clear()
    load_dotenv(_env_path, override=True)
    # Re-set each var via monkeypatch so cleanup restores originals
    for key, value in os.environ.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()


class TestDatabaseConnection:
    @pytest.mark.asyncio
    async def test_can_connect_to_supabase(self):
        """Verify asyncpg can connect to Supabase Postgres."""
        import asyncpg

        from src.config import get_settings

        settings = get_settings()
        conn = await asyncpg.connect(settings.database_url)
        try:
            result = await conn.fetchval("SELECT 1")
            assert result == 1
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_users_table_exists(self):
        """Verify users table exists with expected columns."""
        import asyncpg

        from src.config import get_settings

        settings = get_settings()
        conn = await asyncpg.connect(settings.database_url)
        try:
            cols = await conn.fetch(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'users' ORDER BY ordinal_position"
            )
            col_names = [r["column_name"] for r in cols]
            assert "id" in col_names
            assert "wa_id" in col_names
            assert "name" in col_names
            assert "role" in col_names
            assert "city" in col_names
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_listings_table_has_vector_column(self):
        """Verify listings table has embedding vector column."""
        import asyncpg

        from src.config import get_settings

        settings = get_settings()
        conn = await asyncpg.connect(settings.database_url)
        try:
            row = await conn.fetchrow(
                "SELECT udt_name FROM information_schema.columns "
                "WHERE table_name = 'listings' AND column_name = 'embedding'"
            )
            assert row is not None, "embedding column missing from listings table"
            assert row["udt_name"] == "vector"
        finally:
            await conn.close()

    @pytest.mark.asyncio
    async def test_matches_table_exists(self):
        """Verify matches table exists."""
        import asyncpg

        from src.config import get_settings

        settings = get_settings()
        conn = await asyncpg.connect(settings.database_url)
        try:
            row = await conn.fetchval(
                "SELECT EXISTS(SELECT 1 FROM information_schema.tables "
                "WHERE table_name = 'matches')"
            )
            assert row is True
        finally:
            await conn.close()


class TestGeminiConnection:
    @pytest.mark.asyncio
    async def test_gemini_llm_responds(self):
        """Verify Gemini LLM can generate a response."""
        from src.services.gemini import get_llm

        llm = get_llm()
        response = await llm.ainvoke("Reply with exactly: OK")
        assert response.content is not None
        assert len(response.content) > 0

    @pytest.mark.asyncio
    async def test_gemini_structured_output(self):
        """Verify Gemini structured output works with ClassifiedIntent."""
        from langchain_core.messages import HumanMessage, SystemMessage

        from src.models.intent import ClassifiedIntent
        from src.services.gemini import get_llm

        llm = get_llm()
        classifier = llm.with_structured_output(ClassifiedIntent)
        result = await classifier.ainvoke(
            [
                SystemMessage(content="Classify the user intent. Options: help, unknown."),
                HumanMessage(content="How does this work?"),
            ]
        )
        assert isinstance(result, ClassifiedIntent)
        assert result.intent in ["help", "unknown"]
        assert 0.0 <= result.confidence <= 1.0


class TestEmbeddingsConnection:
    @pytest.mark.asyncio
    async def test_generate_embedding(self):
        """Verify Gemini embedding generation returns correct dimensions."""
        from src.services.embeddings import generate_embedding

        embedding = await generate_embedding("A cozy apartment in Berlin Kreuzberg")
        assert isinstance(embedding, list)
        assert len(embedding) == 768
        assert all(isinstance(v, float) for v in embedding)
