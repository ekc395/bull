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

    # Algorithm-first short mode. The active strategy supplies the candidate
    # the LLM reviews, the executed trade, and the bracket exit levels; every
    # registered strategy is still evaluated and stored for the tournament.
    # Must name a key in strategy.REGISTRY (agent.py falls back to the first
    # registered strategy with a logged warning if it doesn't).
    bull_active_strategy: str = "pullback-v1"
    # Fixed testing universe: comma-separated tickers for the watchlist batch
    # run and the backtest default. 8 liquid names across sectors; edit freely.
    bull_watchlist: str = "AAPL,MSFT,NVDA,AMZN,META,JPM,UNH,XOM"

    database_url: str = "sqlite+aiosqlite:///./bull.db"


settings = Settings()  # type: ignore[call-arg]
