# Bull

A swing trading agent. Given a ticker, it analyzes price history, support/resistance levels, fundamentals, supply-chain dependencies, and recent news, then returns a BUY / HOLD / SELL verdict with a detailed report.

Powered by Claude (`claude-opus-4-7`) with tool use, wrapped in a Streamlit dashboard.

> Status: scaffolding. See [`plan.md`](./plan.md) for the design.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in ANTHROPIC_API_KEY
```

## Run

```bash
streamlit run app.py
```

## Disclaimer

Not financial advice. For research and educational purposes only.
