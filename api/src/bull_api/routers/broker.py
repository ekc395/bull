"""Alpaca paper-trading endpoints: account, positions, orders."""

import asyncio
import logging
from typing import Any

import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ..broker import alpaca
from ..config import settings
from ..db import get_session
from ..models import Order
from ..policy.analysis import collect_outcomes
from ..policy.gate import decision_for_verdict
from ..repos import orders as orepo
from ..repos import policy as prepo
from ..repos import verdicts as vrepo
from ..schemas import (
    AccountResponse,
    ExecuteOrderRequest,
    OrderResponse,
    PortfolioHistoryResponse,
    PositionResponse,
)
from ..strategy import MAX_HOLD_TRADING_DAYS
from ..time import now_utc, trading_day

logger = logging.getLogger(__name__)
router = APIRouter()


def _order_to_response(o: Order) -> OrderResponse:
    return OrderResponse(
        id=o.id,
        alpaca_order_id=o.alpaca_order_id,
        ticker=o.ticker,
        side=o.side,  # type: ignore[arg-type]
        qty=o.qty,
        notional=o.notional,
        status=o.status,
        submitted_at=o.submitted_at,
        filled_avg_price=o.filled_avg_price,
        order_class=o.order_class,
        stop_price=o.stop_price,
        target_price=o.target_price,
        exit_reason=o.exit_reason,
    )


@router.get("/account", response_model=AccountResponse)
async def get_account() -> AccountResponse:
    try:
        data = await asyncio.to_thread(alpaca.get_account)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return AccountResponse(**data)


@router.get("/positions", response_model=list[PositionResponse])
async def get_positions() -> list[PositionResponse]:
    try:
        data = await asyncio.to_thread(alpaca.get_positions)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return [PositionResponse(**p) for p in data]


# Allowed values mirror Alpaca's portfolio-history API. The frontend's range
# toggle is the only intended caller, but we validate explicitly so a typo'd
# URL doesn't get forwarded to Alpaca and surface as an opaque 422.
_ALLOWED_PERIODS = {"1D", "1W", "1M", "3M", "1Y"}
_ALLOWED_TIMEFRAMES = {"1Min", "5Min", "15Min", "1H", "1D"}


@router.get("/portfolio/history", response_model=PortfolioHistoryResponse)
async def get_portfolio_history(
    period: str = "1M", timeframe: str | None = None
) -> PortfolioHistoryResponse:
    if period not in _ALLOWED_PERIODS:
        raise HTTPException(
            status_code=400,
            detail=f"period must be one of {sorted(_ALLOWED_PERIODS)}",
        )
    if timeframe is not None and timeframe not in _ALLOWED_TIMEFRAMES:
        raise HTTPException(
            status_code=400,
            detail=f"timeframe must be one of {sorted(_ALLOWED_TIMEFRAMES)}",
        )
    try:
        data = await asyncio.to_thread(alpaca.get_portfolio_history, period, timeframe)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    return PortfolioHistoryResponse(**data)


@router.post("/orders", response_model=OrderResponse)
async def place_order(req: ExecuteOrderRequest, session: AsyncSession = Depends(get_session)) -> OrderResponse:
    verdict = await vrepo.get_by_id(req.verdict_id, session)
    if verdict is None:
        raise HTTPException(status_code=404, detail=f"Verdict {req.verdict_id} not found")
    if verdict.action == "HOLD":
        raise HTTPException(
            status_code=400, detail="Cannot execute a HOLD verdict — no order to place"
        )

    side = "buy" if verdict.action == "BUY" else "sell"

    # Amount: caller may pass either `notional` (dollars) or `qty` (shares).
    # A passed amount is a manual override and bypasses the policy entirely.
    # If neither is passed, size from the learning-layer policy (Phase 3).
    notional: float | None = req.notional
    qty: float | None = req.qty
    if notional is None and qty is None:
        try:
            account = await asyncio.to_thread(alpaca.get_account)
        except RuntimeError as e:
            raise HTTPException(status_code=503, detail=str(e)) from e

        # Record the policy's decision so it can be forward-tested later. A
        # deliberate click still executes at >= base size even when the policy
        # advises against acting; the persisted decision captures that it
        # declined (and why).
        outcomes = await collect_outcomes(session)
        decision = decision_for_verdict(verdict, outcomes)
        await prepo.insert_decision(decision, verdict.id, session)
        size_pct = (
            decision.size_pct
            if decision.act and decision.size_pct > 0
            else settings.bull_position_size_pct
        )
        notional = round(account["equity"] * size_pct / 100, 2)
        if notional <= 0:
            raise HTTPException(
                status_code=400, detail=f"Computed notional ${notional} is non-positive"
            )

    # Short-mode strategy BUYs execute as bracket orders: the rule's stop and
    # target become GTC legs and Alpaca runs the exits server-side. Everything
    # else keeps the plain market path.
    algo = verdict.algo_json or {}
    active_eval = (algo.get("evaluations") or {}).get(algo.get("active_strategy") or "")
    bracket_plan = (
        active_eval
        if (
            verdict.timeframe == "short"
            and side == "buy"
            and verdict.candidate_action == "BUY"
            and active_eval is not None
            and active_eval.get("stop") is not None
            and active_eval.get("target") is not None
        )
        else None
    )

    if bracket_plan is not None:
        if qty is not None:
            shares = int(qty)  # brackets reject fractionals — floor
        else:
            prices = (verdict.facts_bundle_json or {}).get("prices") or []
            last_close = float(prices[-1].get("close") or 0) if prices else 0.0
            if last_close <= 0:
                raise HTTPException(
                    status_code=400,
                    detail="Verdict has no last close to size a bracket order from",
                )
            shares = int((notional or 0) // last_close)
        if shares < 1:
            # No silent fallback to an unprotected market order: a strategy
            # entry without its stop/target legs would be a different trade.
            raise HTTPException(
                status_code=422,
                detail=(
                    "Position size is below one whole share and bracket orders "
                    "cannot use fractional/notional amounts. Pass a larger "
                    "notional or qty to execute this strategy trade."
                ),
            )
        alpaca_resp = await asyncio.to_thread(
            alpaca.place_bracket_order,
            verdict.ticker,
            shares,
            bracket_plan["stop"],
            bracket_plan["target"],
        )
    else:
        alpaca_resp = await asyncio.to_thread(
            alpaca.place_order, verdict.ticker, side, notional, qty
        )

    order = Order(
        verdict_id=verdict.id,
        alpaca_order_id=alpaca_resp["alpaca_order_id"],
        ticker=verdict.ticker,
        side=side,
        qty=alpaca_resp.get("qty") or (shares if bracket_plan is not None else qty),
        notional=alpaca_resp.get("notional") or notional,
        status=alpaca_resp["status"],
        submitted_at=alpaca_resp["submitted_at"] or now_utc(),
        filled_avg_price=alpaca_resp.get("filled_avg_price") or None,
        order_class="bracket" if bracket_plan else "simple",
        stop_price=bracket_plan["stop"] if bracket_plan else None,
        target_price=bracket_plan["target"] if bracket_plan else None,
        legs_json=alpaca_resp.get("legs") if bracket_plan else None,
    )
    persisted = await orepo.insert(order, session)
    return _order_to_response(persisted)


@router.delete("/positions/{symbol}")
async def close_position(symbol: str, session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    symbol = symbol.strip().upper()
    if not symbol:
        raise HTTPException(status_code=400, detail="symbol is required")
    try:
        # Live bracket legs hold the shares — Alpaca rejects the close until
        # they're cancelled. No-op for positions without open orders.
        await asyncio.to_thread(alpaca.cancel_open_orders, symbol)
        resp = await asyncio.to_thread(alpaca.close_position, symbol)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    # Persist the close-order so the trade journal sees both legs of the round trip.
    order = Order(
        verdict_id=None,
        alpaca_order_id=resp["alpaca_order_id"],
        ticker=symbol,
        side=resp.get("side") or "sell",
        qty=None,
        notional=None,
        status=resp["status"],
        submitted_at=resp["submitted_at"] or now_utc(),
        filled_avg_price=None,
        order_class="simple",
        exit_reason="manual",
    )
    await orepo.insert(order, session)
    return resp


async def sweep(session: AsyncSession) -> dict[str, Any]:
    """Time-stop enforcement + exit reconciliation. Callable directly (the
    autotrade loop runs it before sizing new trades) or via the endpoint below.

    1. Any open position whose originating bracket entry is older than
       MAX_HOLD_TRADING_DAYS gets its legs cancelled and is closed at market
       (`exit_reason="time_stop"`). Stop/target exits need no sweep — Alpaca
       fills those server-side.
    2. Filled bracket legs that happened Alpaca-side since the last sweep are
       inserted as local sell Orders (linked to the entry's verdict) so the
       trade journal shows the full round trip.
    3. Local rows inserted at submission time (market buys, manual closes,
       time stops) carry no fill data — backfill status/qty/filled_avg_price
       from Alpaca once filled, so /trades can compute realized P&L.
    """
    try:
        positions = await asyncio.to_thread(alpaca.get_positions)
        recent_alpaca = await asyncio.to_thread(alpaca.get_recent_orders, 100)
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e

    local = await orepo.list_recent(1000, session)  # newest first
    known_ids = {o.alpaca_order_id for o in local}
    today = trading_day()

    closed: list[str] = []
    for pos in positions:
        symbol = pos["symbol"]
        entry = next(
            (
                o
                for o in local
                if o.ticker == symbol and o.order_class == "bracket" and o.side == "buy"
            ),
            None,
        )
        if entry is None:
            continue  # not a strategy trade — no time stop applies
        age_days = int(np.busday_count(trading_day(entry.submitted_at), today))
        if age_days < MAX_HOLD_TRADING_DAYS:
            continue
        await asyncio.to_thread(alpaca.cancel_open_orders, symbol)
        resp = await asyncio.to_thread(alpaca.close_position, symbol)
        await orepo.insert(
            Order(
                verdict_id=entry.verdict_id,
                alpaca_order_id=resp["alpaca_order_id"],
                ticker=symbol,
                side="sell",
                status=resp["status"],
                submitted_at=resp["submitted_at"] or now_utc(),
                order_class="simple",
                exit_reason="time_stop",
            ),
            session,
        )
        closed.append(symbol)
        logger.info("sweep: time-stopped %s after %d trading days", symbol, age_days)

    # Backfill: rows are persisted from the submission response, so market
    # orders start with no fill (and manual/time-stop closes with no qty).
    # `filled_qty` covers notional entries where qty is unknown at submit.
    local_by_alpaca_id = {o.alpaca_order_id: o for o in local}
    backfilled: list[str] = []
    for r in recent_alpaca:
        o = local_by_alpaca_id.get(r["alpaca_order_id"])
        if o is None or r["status"] != "filled":
            continue
        if o.status == "filled" and o.filled_avg_price is not None and o.qty is not None:
            continue
        o.status = r["status"]
        o.filled_avg_price = o.filled_avg_price or r.get("filled_avg_price") or None
        o.qty = o.qty or r.get("qty") or r.get("filled_qty") or None
        backfilled.append(o.alpaca_order_id)
    if backfilled:
        await session.commit()

    # Reconcile: map known bracket leg ids → exit reason, insert missing fills.
    leg_index: dict[str, tuple[Order, str]] = {}
    for o in local:
        if o.order_class == "bracket" and o.legs_json:
            if o.legs_json.get("stop_loss"):
                leg_index[o.legs_json["stop_loss"]] = (o, "stop")
            if o.legs_json.get("take_profit"):
                leg_index[o.legs_json["take_profit"]] = (o, "target")

    reconciled: list[str] = []
    for r in recent_alpaca:
        rid = r["alpaca_order_id"]
        if rid in known_ids or rid not in leg_index or r["status"] != "filled":
            continue
        parent, reason = leg_index[rid]
        await orepo.insert(
            Order(
                verdict_id=parent.verdict_id,
                alpaca_order_id=rid,
                ticker=r["symbol"],
                side="sell",
                qty=r.get("qty") or None,
                status=r["status"],
                submitted_at=r["submitted_at"] or now_utc(),
                filled_avg_price=r.get("filled_avg_price") or None,
                order_class="simple",
                exit_reason=reason,
            ),
            session,
        )
        reconciled.append(rid)

    return {
        "checked_positions": len(positions),
        "closed": closed,
        "backfilled": backfilled,
        "reconciled": reconciled,
    }


@router.post("/positions/sweep")
async def sweep_positions(session: AsyncSession = Depends(get_session)) -> dict[str, Any]:
    """Manual trigger for `sweep` (cron it yourself if you want), same
    convention as scoring."""
    return await sweep(session)
