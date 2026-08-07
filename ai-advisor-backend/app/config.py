from functools import lru_cache
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    log_level: str = "INFO"
    log_file: str = "logs/advisor.jsonl"
    log_max_bytes: int = 10_485_760
    log_backup_count: int = 5
    log_chat_content: bool = True
    talent_data_source: str = "json"
    candidate_profiles_file: str = "candidate_profiles-01 3.json"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.5-flash-lite"
    database_url: str = (
        "mssql+pymssql://zlanze_ai_reader:"
        "ChangeThisReaderPassword_2026!@localhost:1433/ZLANZE_PROD"
    )
    redis_url: str = "redis://localhost:6379/0"
    context_ttl_seconds: int = 1800
    max_developers: int = 5
    marketplace_currency: str = "USD"
    sql_query_timeout_seconds: int = 10
    cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
