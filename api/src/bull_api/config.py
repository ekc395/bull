"""Settings loaded from .env via pydantic-settings."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Optional so cost-free, no-LLM jobs (autotrade, scoring) run without it —
    # e.g. the GitHub Actions cron never constructs an Anthropic client. The
    # /analyze path then fails at call time (auth error) instead of at import.
    anthropic_api_key: str = ""
    alpaca_api_key: str = ""
    alpaca_api_secret: str = ""
    finnhub_api_key: str = ""
    alphavantage_api_key: str = ""

    bull_model: str = "claude-opus-4-8"
    bull_position_size_pct: float = Field(default=2.0, gt=0, le=100)

    # Phase 4 (Part B): when set, agent.py appends the model's own past
    # verdict→outcome track record for similar setups to the uncached user
    # message. Default off — it adds input tokens per analysis.
    bull_outcome_feedback: bool = False

    # Algorithm-first short mode. The active strategy supplies the candidate
    # the LLM reviews, the executed trade, and the bracket exit levels; every
    # registered strategy is still evaluated and stored for the tournament.
    # Must name a key in strategy.REGISTRY (agent.py falls back to the first
    # registered strategy with a logged warning if it doesn't).
    # turtle-20-v1 won the 2026-06 Dow-30 regime-split tournament (best P&L in
    # both halves, t≈2.8 on ~1,000 trades) — see plan.md → strategy tournament.
    bull_active_strategy: str = "turtle-20-v1"
    # Fixed testing universe: comma-separated tickers for the watchlist batch
    # run and the backtest default. 8 liquid names across sectors; edit freely.
    bull_watchlist: str = "AAPL,MSFT,NVDA,AMZN,META,JPM,UNH,XOM"
    # Screener universe (bull_api.screen / GET /screen). Empty = the current
    # S&P 500 constituents (fetched once per trading day; index membership is
    # the quality/liquidity floor); set a comma-separated list to pin it
    # manually. Size 0 = scan the whole index; >0 trims for quicker runs.
    bull_screen_universe: str = ""
    bull_screen_size: int = 0
    # Max new positions the unattended autotrade loop opens per run
    # (bull_api.autotrade). The policy gate caps each at 5% equity, so the
    # default 3 is ≤~15% fresh exposure per trading day.
    bull_autotrade_max_new: int = 3

    database_url: str = "sqlite+aiosqlite:///./bull.db"


settings = Settings()  # type: ignore[call-arg]
