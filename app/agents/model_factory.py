"""LLM model factory supporting OpenAI and Anthropic via configuration."""

from langchain.chat_models import init_chat_model
from langchain_core.language_models.chat_models import BaseChatModel

from app.config import Settings, get_settings


def create_chat_model(settings: Settings | None = None) -> BaseChatModel:
    """Create a chat model for the configured provider."""
    settings = settings or get_settings()
    settings.require_llm_credentials()

    if settings.llm_provider == "openai":
        return init_chat_model(
            settings.model_name,
            model_provider="openai",
            api_key=settings.openai_api_key,
        )
    if settings.llm_provider == "anthropic":
        return init_chat_model(
            settings.model_name,
            model_provider="anthropic",
            api_key=settings.anthropic_api_key,
        )
    raise ValueError(f"Unsupported LLM provider: {settings.llm_provider}")
