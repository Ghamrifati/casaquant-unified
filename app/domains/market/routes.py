"""CasaQuant Unified — Market data API routes."""

from datetime import date
from typing import Sequence

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from app.dependencies import DBDep
from app.domains.market.models import MarketFeature, MarketSnapshot, OHLCV, Ticker
from app.domains.market.repository import (
    get_latest_snapshot,
    get_market_features,
    get_ohlcv_for_ticker,
    get_snapshots_for_ticker,
    get_tickers,
)

router = APIRouter()


@router.get("/tickers", response_model=list[Ticker])
async def list_tickers(
    db: DBDep,
    actif_only: bool = Query(default=True),
):
    """List all BVC tickers."""
    return get_tickers(db, actif_only)


@router.get("/tickers/{ticker_id}")
async def get_ticker(ticker_id: int, db: DBDep):
    """Get a single ticker by ID."""
    tickers = get_tickers(db, actif_only=False)
    for t in tickers:
        if t.id == ticker_id:
            return t
    raise HTTPException(status_code=404, detail="Ticker not found")


@router.get("/tickers/{ticker_id}/ohlcv", response_model=list[OHLCV])
async def ticker_ohlcv(
    ticker_id: int,
    db: DBDep,
    days: int = Query(default=252, ge=1, le=5000),
    start: date | None = None,
    end: date | None = None,
):
    """Get OHLCV history for a ticker."""
    return get_ohlcv_for_ticker(db, ticker_id, start, end, limit=days)


@router.get("/tickers/{ticker_id}/snapshots", response_model=list[MarketSnapshot])
async def ticker_snapshots(
    ticker_id: int,
    db: DBDep,
    trade_date: date | None = Query(default=None),
):
    """Get intraday snapshots for a ticker."""
    return get_snapshots_for_ticker(db, ticker_id, trade_date)


@router.get("/snapshots/latest")
async def latest_snapshot(
    db: DBDep,
    ticker_id: int | None = Query(default=None),
):
    """Get the latest market snapshot across all tickers."""
    snap = get_latest_snapshot(db, ticker_id)
    if not snap:
        raise HTTPException(status_code=404, detail="No snapshots found")
    return snap


@router.get("/features", response_model=list[MarketFeature])
async def list_features(
    db: DBDep,
    ticker_id: int | None = Query(default=None),
    trade_date: date | None = Query(default=None),
):
    """Get computed daily features (EOD OHLCV aggregates)."""
    return get_market_features(db, ticker_id, trade_date)
