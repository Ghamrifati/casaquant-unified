"""CasaQuant Unified — Backtest API routes."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from app.dependencies import DBDep

router = APIRouter()


@router.get("/v4/{ticker_id}")
async def get_backtest_v4(
    ticker_id: int,
    db: DBDep,
    days: int = Query(default=252 * 5, ge=100),
):
    """Get V4.1 backtest results for a ticker."""
    # TODO: implement
    return {"status": "ok", "ticker_id": ticker_id, "strategy": "v4"}


@router.get("/v7/{ticker_id}")
async def get_backtest_v7(
    ticker_id: int,
    db: DBDep,
    days: int = Query(default=252 * 5, ge=100),
):
    """Get V7 backtest results for a ticker."""
    # TODO: implement
    return {"status": "ok", "ticker_id": ticker_id, "strategy": "v7"}


@router.post("/v4/run/{ticker_id}")
async def run_backtest_v4(ticker_id: int, db: DBDep):
    """Run V4.1 backtest for a ticker (async via Celery)."""
    # TODO: queue backtest via Celery
    return {"status": "queued", "ticker_id": ticker_id, "strategy": "v4"}
