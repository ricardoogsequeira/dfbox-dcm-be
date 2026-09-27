from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "dfbox-dcm-be"
    environment: str = Field(default="local", alias="APP_ENVIRONMENT")
    log_level: str = "INFO"
    database_url: str = "postgresql+asyncpg://dcmadmin:change-me@localhost:5432/appdb"
    cors_allowed_origins: list[str] = ["http://localhost:4200", "http://127.0.0.1:4200"]
    genai_model_endpoint: str | None = None
    genai_api_key: str | None = None
    genai_model_name: str | None = None
    genai_api_key_header: str = "api-key"
    genai_api_key_prefix: str = ""
    genai_timeout_seconds: float = 30.0
    genai_system_prompt: str = (
        "You are the Digital Factory Delivery & Capacity Manager assistant. "
        "Help users understand projects, developers, weekly capacity, and allocation rules. "
        "Do not invent Jira mappings or security permissions."
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
