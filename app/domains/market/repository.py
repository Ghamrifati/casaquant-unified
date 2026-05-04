"""CasaQuant Unified — Market data repository (bulk queries, N+1 fix).

All DB access for market data goes through here.
"""

from datetime import date, datetime
from typing import Sequence

from sqlmodel import Session, select

from app.domains.market.models import OHLCV, MarketFeature, MarketSnapshot, Ticker


def get_tickers(session: Session, actif_only: bool = True) -> Sequence[Ticker]:
    """Get all tickers, optionally filtering active only."""
    stmt = select(Ticker)
    if actif_only:
        stmt = stmt.where(Ticker.actif == True)  # noqa: E712
    return session.exec(stmt).all()


def get_ohlcv_for_ticker(
    session: Session,
    ticker_id: int,
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = 252,
) -> Sequence[OHLCV]:
    """Get OHLCV rows for a ticker, optionally filtered by date range."""
    stmt = (
        select(OHLCV)
        .where(OHLCV.ticker_id == ticker_id)
        .order_by(OHLCV.date.desc())
        .limit(limit)
    )
    if start_date:
        stmt = stmt.where(OHLCV.date >= start_date)
    if end_date:
        stmt = stmt.where(OHLCV.date <= end_date)
    return session.exec(stmt).all()


def get_latest_snapshot(
    session: Session,
    ticker_id: int | None = None,
) -> MarketSnapshot | None:
    """Get the latest market snapshot for a ticker (or any ticker if None)."""
    stmt = select(MarketSnapshot).order_by(MarketSnapshot.session_time.desc())
    if ticker_id:
        stmt = stmt.where(MarketSnapshot.ticker_id == ticker_id)
    return session.exec(stmt.limit(1)).first()


def get_snapshots_for_ticker(
    session: Session,
    ticker_id: int,
    trade_date: date | None = None,
) -> Sequence[MarketSnapshot]:
    """Get all snapshots for a ticker on a given date."""
    stmt = (
        select(MarketSnapshot)
        .where(MarketSnapshot.ticker_id == ticker_id)
        .order_by(MarketSnapshot.session_time.asc())
    )
    if trade_date:
        start = datetime.combine(trade_date, datetime.min.time())
        end = datetime.combine(trade_date, datetime.max.time())
        stmt = stmt.where(
            MarketSnapshot.session_time >= start,
            MarketSnapshot.session_time <= end,
        )
    return session.exec(stmt).all()


def get_market_features(
    session: Session,
    ticker_id: int | None = None,
    trade_date: date | None = None,
) -> Sequence[MarketFeature]:
    """Get computed daily features."""
    stmt = select(MarketFeature)
    if ticker_id:
        stmt = stmt.where(MarketFeature.ticker_id == ticker_id)
    if trade_date:
        stmt = stmt.where(MarketFeature.date == trade_date)
    return session.exec(stmt.order_by(MarketFeature.date.desc())).all()
