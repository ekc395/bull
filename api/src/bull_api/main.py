"""FastAPI entrypoint. See plan.md."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import (
    analyze,
    broker,
    financials,
    fundamentals,
    history,
    news,
    policy,
    prices,
    scores,
    screen,
    seasonals,
    verdicts,
)

app = FastAPI(title="Bull API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analyze.router)
app.include_router(prices.router)
app.include_router(fundamentals.router)
app.include_router(financials.router)
app.include_router(seasonals.router)
app.include_router(verdicts.router)
app.include_router(broker.router)
app.include_router(history.router)
app.include_router(news.router)
app.include_router(scores.router)
app.include_router(screen.router)
app.include_router(policy.router)


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    return {"status": "ok"}
