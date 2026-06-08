"""Settings loaded from .env via pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str
    alpaca_api_key: str = ""
    alpaca_api_secret: str = ""
    finnhub_api_key: str = ""
    alphavantage_api_key: str = ""

    bull_model: str = "claude-opus-4-8"
    bull_position_size_pct: float = 2.0

    # Phase 4 (Part B): when set, agent.py appends the model's own past
    # verdict→outcome track record for similar setups to the uncached user
    # message. Default off — it adds input tokens per analysis.
    bull_outcome_feedback: bool = False

    database_url: str = "sqlite+aiosqlite:///./bull.db"


settings = Settings()  # type: ignore[call-arg]
