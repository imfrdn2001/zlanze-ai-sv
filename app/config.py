import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


_CONFIG = json.loads(Path(__file__).with_name("config.json").read_text(encoding="utf-8"))
_LOGGING = _CONFIG["logging"]
_TALENT = _CONFIG["talent"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = _CONFIG["app_env"]
    log_level: str = _LOGGING["level"]
    log_file: str = _LOGGING["file"]
    log_max_bytes: int = _LOGGING["max_bytes"]
    log_backup_count: int = _LOGGING["backup_count"]
    log_chat_content: bool = _LOGGING["log_chat_content"]
    talent_data_source: str = _TALENT["data_source"]
    candidate_profiles_file: str = _TALENT["candidate_profiles_file"]
    gemini_api_key: str = ""
    gemini_model: str = _CONFIG["gemini_model"]
    database_url: str = (
        "mssql+pymssql://zlanze_ai_reader:"
        "ChangeThisReaderPassword_2026!@localhost:1433/ZLANZE_PROD"
    )
    redis_url: str = ""
    context_ttl_seconds: int = _CONFIG["context_ttl_seconds"]
    max_developers: int = _TALENT["max_developers"]
    marketplace_currency: str = _TALENT["marketplace_currency"]
    sql_query_timeout_seconds: int = _CONFIG["sql_query_timeout_seconds"]
    cors_origins: Annotated[list[str], NoDecode] = _CONFIG["cors_origins"]

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
