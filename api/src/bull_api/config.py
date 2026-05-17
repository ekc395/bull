"""Settings loaded from .env via pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str
    alpaca_api_key: str = ""
    alpaca_api_secret: str = ""
    finnhub_api_key: str = ""
    alphavantage_api_key: str = ""

    bull_primary_model: str = "claude-sonnet-4-6"
    bull_deeper_model: str = "claude-opus-4-7"
    bull_escalation_confidence_threshold: int = 60
    bull_position_size_pct: float = 2.0

    database_url: str = "sqlite+aiosqlite:///./bull.db"


settings = Settings()  # type: ignore[call-arg]
