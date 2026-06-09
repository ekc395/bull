# Bull

Swing trading agent powered by Claude. Enter a ticker → the agent fetches price history, indicators, support/resistance, fundamentals, recent news, and market context, then synthesizes a **BUY / HOLD / SELL** verdict with a structured report. Verdicts can be executed as paper trades through Alpaca and tracked over time.

> Not financial advice. For research and educational use only.

## What it does

- **Single-ticker analysis** (`/ticker/[symbol]`) — paste a ticker, get a verdict and full report. Inputs: RSI / MACD / SMAs / ATR, deterministic support/resistance from pivots, fundamentals (P/E, margins, growth, signed `days_until_earnings`, analyst targets), 7-day news, and market context (SPY trend, sector ETF trend, VIX state).
- **Structural-thesis reasoning on every analysis** — Claude reasons from its own training knowledge about industry supply/demand, market-structure moat, geopolitical positioning, and multi-quarter catalysts. A strong structural read can lift confidence past short-term technicals, but hard gates (broken sector trend, earnings ≤7 days out, VIX "high") still apply.
- **Verdict caching** — keyed by `(ticker, ET trading day)`. Same ticker on the same NYSE session returns the cached row, no LLM call. Bypass with `force=true`.
- **Paper trading via Alpaca** — `paper=True` is hardcoded; there is no path that constructs a live client. Position sizing defaults to 2% of equity (`BULL_POSITION_SIZE_PCT`).
- **Portfolio + journal** — equity curve, current positions, and a verdict history with realized-return scoring at fixed trading-day horizons.
- **Outcome-feedback learning layer** (`policy/`) — a rule wrapped around the fixed prompt + pipeline, learned from realized outcomes rather than by training the model (outcomes are pooled across models, so the track record survives model switches). It calibrates confidence and per-setup edge (`GET /policy/calibration`), gates and sizes trades (each verdict carries an advisory act/size decision; `POST /orders` sizes from it), and can optionally feed the model the system's past outcomes for similar setups (`BULL_OUTCOME_FEEDBACK`, off by default). Degrades gracefully — guardrails-only at base size until enough verdicts are scored.

## Stack

- **Backend** (`api/`): FastAPI · Pydantic v2 · SQLAlchemy 2.0 · Alembic · SQLite
- **Frontend** (`web/`): Next.js 15 (App Router) · TypeScript · Tailwind · shadcn/ui · TradingView `lightweight-charts` · TanStack React Query
- **Agent**: Anthropic SDK — `claude-opus-4-8` by default. **Deterministic tool fetch + single-shot synthesis** (no tool-use loop). Override the model with `BULL_MODEL`.
- **Data**: yfinance, Google News RSS (via `feedparser`), Finnhub and Alpha Vantage (both optional, used as fundamentals fallbacks), Alpaca paper-trading

## Setup

### Requirements

- Python ≥ 3.11
- Node ≥ 20
- [`uv`](https://github.com/astral-sh/uv) for Python dependency management
- An **Anthropic API key** with credits — get one at [console.anthropic.com](https://console.anthropic.com). Note: a Claude.ai Pro subscription does **not** grant API credits; billing is separate.
- Optional: Alpaca paper API key + secret (free at [alpaca.markets/paper](https://alpaca.markets/paper)) if you want to execute trades.

### Backend

```bash
cd api
uv venv && uv pip install -e .
alembic upgrade head
```

Create `api/.env` with at minimum:

```
ANTHROPIC_API_KEY=sk-ant-...
```

Optional vars (all default to empty / sensible values):

```
ALPACA_API_KEY=
ALPACA_API_SECRET=
FINNHUB_API_KEY=
ALPHAVANTAGE_API_KEY=
BULL_MODEL=claude-opus-4-8
BULL_POSITION_SIZE_PCT=2.0
BULL_OUTCOME_FEEDBACK=false          # feed the model the system's past outcomes (adds input tokens)
DATABASE_URL=sqlite+aiosqlite:///./bull.db
```

Run the dev server:

```bash
./dev.sh                             # http://localhost:8000 (docs at /docs)
```

`dev.sh` activates the venv and exports `PYTHONPATH=src` before launching uvicorn. The `PYTHONPATH` step works around a uv + CPython 3.13 issue on macOS where uv marks `.venv` as hidden and CPython 3.13's `site.py` then skips `.pth` files, breaking the editable install. Bypassing `.pth` resolution avoids the problem on every platform.

### Frontend

```bash
cd web
cp .env.example .env.local           # default points at http://localhost:8000
npm install
npm run dev                          # http://localhost:3000
```

## Cost

The only paid surface is the Anthropic API. Everything else (yfinance, Google News RSS, Alpaca paper, Finnhub/Alpha Vantage free tiers) costs nothing.

| Model                         | Approx. cost / analysis |
| ----------------------------- | ----------------------- |
| `claude-opus-4-8` (default)   | $0.10 – $0.15           |
| `claude-sonnet-4-6`           | $0.02 – $0.03           |
| `claude-haiku-4-5-20251001`   | $0.005 – $0.01          |

Switch models via the `BULL_MODEL` env var. Same-day re-analyses of a ticker hit the verdict cache for free.

## Tests

```bash
cd api
uv pip install -e ".[dev]"
pytest
```

## Project layout

```
api/                            FastAPI backend
  src/bull_api/
    agent.py                    facts fetch + single-shot Opus synthesis
    prompts.py                  system prompt (structural thesis, calibration, gates)
    checks.py                   compute_signals (shared) + post-verdict warnings
    policy/                     learning layer: features, analysis, gate, recall
    tools/                      prices, indicators, support_resistance,
                                fundamentals, news, supply_chain, market_context
    routers/                    analyze, prices, verdicts, broker, history,
                                news, scores, policy
    broker/alpaca.py            paper-trading wrapper (paper=True hardcoded)
  alembic/                      migrations
web/                            Next.js frontend
  src/app/                      App Router pages — dashboard, ticker
  src/components/               chart, verdict banner, indicator table, etc.
```

## Disclaimer

Bull is for research and educational use only. **Not financial advice.** Every rendered verdict/report includes this disclaimer; do not remove it. Paper trading is hardcoded — there is no path that constructs a live Alpaca client.
