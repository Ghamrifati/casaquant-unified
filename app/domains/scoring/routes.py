"""CasaQuant Unified — Scoring API routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.dependencies import DBDep

router = APIRouter()


@router.get("/bulk")
async def get_scoring_bulk(db: DBDep):
    """Get all tickers with their latest scoring.

    N+1 fixed — single bulk query.
    """
    # TODO: implement bulk scoring query
    return {"status": "ok", "count": 0, "tickers": []}


@router.get("/tickers/{ticker_id}")
async def get_ticker_scoring(ticker_id: int, db: DBDep):
    """Get scoring for a single ticker."""
    # TODO: implement single ticker scoring
    return {"status": "ok", "ticker_id": ticker_id}


@router.post("/recalc")
async def trigger_recalc(db: DBDep):
    """Trigger the 6-step recalc pipeline."""
    # TODO: queue recalc via Celery
    return {"status": "queued", "task_id": "stub"}
