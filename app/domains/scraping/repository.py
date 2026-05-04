"""CasaQuant Unified — Scraping repository (DB access).

Handles bulk insertion of snapshots and features.
"""

import logging
from datetime import date, datetime
from typing import Sequence

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlmodel import Session, select

from app.domains.market.models import MarketSnapshot, Ticker
from app.domains.pipeline.models import IngestionLog

logger = logging.getLogger("casaquant.scraping.repository")


def get_or_create_tickers(session: Session, names: set[str]) -> dict[str, int]:
    """Get or create tickers by name, return mapping name -> id."""
    result: dict[str, int] = {}
    for name in names:
        stmt = select(Ticker).where(Ticker.nom == name)
        existing = session.exec(stmt).first()
        if existing:
            result[name] = existing.id
        else:
            ticker = Ticker(nom=name, code_bc=name.upper().replace(" ", "-"), actif=True)
            session.add(ticker)
            session.flush()
            result[name] = ticker.id
            logger.info("Created new ticker: %s (id=%d)", name, ticker.id)
    return result


def bulk_insert_snapshots(session: Session, snapshots: Sequence[MarketSnapshot]) -> int:
    """Bulk insert market snapshots, skipping duplicates."""
    if not snapshots:
        return 0

    count = 0
    for snap in snapshots:
        # Upsert logic: skip if same ticker + session_time exists
        stmt = select(MarketSnapshot).where(
            MarketSnapshot.ticker_id == snap.ticker_id,
            MarketSnapshot.session_time == snap.session_time,
        )
        if session.exec(stmt).first() is None:
            session.add(snap)
            count += 1

    session.commit()
    logger.info("Inserted %d new snapshots (skipped %d duplicates)", count, len(snapshots) - count)
    return count


def log_ingestion(
    session: Session,
    source: str,
    records_count: int,
    status: str,
    detail: str | None = None,
) -> None:
    """Log ingestion attempt to audit table."""
    log_entry = IngestionLog(
        source=source,
        records_count=records_count,
        status=status,
        detail=detail,
    )
    session.add(log_entry)
    session.commit()
