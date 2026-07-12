"""Application configuration loaded from environment variables."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for the learn-to-teach-agent application."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: Literal["development", "test", "production"] = "development"
    llm_provider: Literal["openai", "anthropic"] = "openai"
    model_name: str = "gpt-4o-mini"
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    database_url: str = (
        "postgresql+psycopg2://lta:lta_secret@localhost:5432/learn_to_teach"
    )
    prompt_version: str = "v1"
    public_base_url: str = "http://localhost:8000"
    admin_username: str = "admin"
    admin_password_hash: str = ""
    session_secret: str = "dev-only-change-me"
    max_upload_bytes: int = Field(default=1_048_576, ge=1024)
    max_image_upload_bytes: int = Field(default=5_242_880, ge=1024)
    data_dir: str = "data"
    prompts_dir: str = "prompts"

    @field_validator("openai_api_key", "anthropic_api_key", mode="before")
    @classmethod
    def empty_str_to_none(cls, value: str | None) -> str | None:
        if value is None or (isinstance(value, str) and not value.strip()):
            return None
        return value

    @model_validator(mode="after")
    def validate_provider_key_when_needed(self) -> "Settings":
        # Keys are validated at generation time, not at import, so health/ready
        # can succeed without calling a paid LLM API.
        return self

    def require_llm_credentials(self) -> None:
        """Raise if the selected provider's API key is missing."""
        if self.llm_provider == "openai" and not self.openai_api_key:
            raise ValueError(
                "OPENAI_API_KEY is required when LLM_PROVIDER=openai"
            )
        if self.llm_provider == "anthropic" and not self.anthropic_api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic"
            )

    @property
    def has_required_config(self) -> bool:
        """True when non-LLM configuration required for readiness is present."""
        return bool(self.database_url and self.session_secret and self.prompt_version)


@lru_cache
def get_settings() -> Settings:
    return Settings()
