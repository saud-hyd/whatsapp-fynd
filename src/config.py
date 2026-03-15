from functools import lru_cache

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # WhatsApp Cloud API
    wa_verify_token: str
    wa_access_token: str
    wa_phone_number_id: str
    wa_app_secret: str = ""  # For webhook signature verification (required in production)

    # Google AI (Gemini)
    google_api_key: str

    # Supabase
    supabase_url: str
    supabase_anon_key: str
    supabase_service_key: str
    database_url: str

    # App
    app_env: str = "development"

    @property
    def wa_api_url(self) -> str:
        return f"https://graph.facebook.com/v23.0/{self.wa_phone_number_id}/messages"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
