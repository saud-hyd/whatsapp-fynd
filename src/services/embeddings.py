from google import genai
from google.genai import types

from src.config import get_settings

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    """Get or create the Gemini client."""
    global _client
    if _client is None:
        _client = genai.Client(api_key=get_settings().google_api_key)
    return _client


async def generate_embedding(
    text: str,
    task_type: str = "RETRIEVAL_DOCUMENT",
) -> list[float]:
    """Generate a 768-dim embedding using Gemini Embedding 2.

    Args:
        text: The text to embed.
        task_type: One of RETRIEVAL_DOCUMENT, RETRIEVAL_QUERY, SEMANTIC_SIMILARITY,
                   CLASSIFICATION, CLUSTERING.
    """
    client = _get_client()
    result = client.models.embed_content(
        model="gemini-embedding-2-preview",
        contents=text,
        config=types.EmbedContentConfig(
            task_type=task_type,
            output_dimensionality=768,
        ),
    )
    return result.embeddings[0].values
