from langchain_google_genai import ChatGoogleGenerativeAI

from src.config import get_settings


def get_llm() -> ChatGoogleGenerativeAI:
    """Get the Gemini LLM instance for structured extraction and conversation."""
    return ChatGoogleGenerativeAI(
        model="gemini-3.1-flash-lite-preview",
        temperature=0,  # Gemini 3+ defaults to 1.0 — must set explicitly for extraction
        google_api_key=get_settings().google_api_key,
    )
