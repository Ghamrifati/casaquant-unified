"""CasaQuant Unified — Pipeline job tracking and recalc models."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlmodel import Field, SQLModel


class JobRun(SQLModel, table=True):
    """Execution tracking for scheduled and manual jobs."""

    __tablename__ = "job_runs"

    id: str = Field(primary_key=True, max_length=36)
    job_type: str = Field(max_length=50)  # 'scrape_intraday' | 'transform_eod' | 'recalc'
    status: str = Field(max_length=20)  # 'running' | 'success' | 'error' | 'quarantine'
    started_at: datetime | None = Field(default_factory=datetime.utcnow)
    ended_at: datetime | None = None
    detail: str | None = None  # JSON string
    error_message: str | None = None


class JusteValeur(SQLModel, table=True):
    """Fair value estimates (as-of-date to prevent look-ahead bias)."""

    __tablename__ = "juste_valeur"

    id: int | None = Field(default=None, primary_key=True)
    ticker_id: int = Field(foreign_key="tickers.id", index=True)
    date: date = Field(index=True)  # type: ignore[name-defined]
    valeur: Decimal | None = Field(default=None, max_digits=12, decimal_places=4)
    per: Decimal | None = Field(default=None, max_digits=5, decimal_places=2)
    dividend_yield: Decimal | None = Field(default=None, max_digits=5, decimal_places=2)
    source: str | None = Field(default=None, max_length=50)

    class Config:
        pass


class IngestionLog(SQLModel, table=True):
    """Data ingestion audit trail."""

    __tablename__ = "ingestion_log"

    id: int | None = Field(default=None, primary_key=True)
    source: str = Field(max_length=50)  # 'casabourse_api' | 'wafabourse_html'
    records_count: int | None = None
    status: str = Field(max_length=20)  # 'success' | 'partial' | 'error'
    detail: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class QualityReport(SQLModel, table=True):
    """End-of-day data quality summary."""

    __tablename__ = "quality_report"

    id: int | None = Field(default=None, primary_key=True)
    date: date = Field(index=True)  # type: ignore[name-defined]
    ticker_coverage_pct: Decimal | None = Field(default=None, max_digits=5, decimal_places=2)
    missing_tickers: int | None = None
    stale_tickers: int | None = None
    quarantine_count: int | None = None
    computed_at: datetime = Field(default_factory=datetime.utcnow)
