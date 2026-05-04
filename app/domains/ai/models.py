"""CasaQuant Unified — AI analysis and cache models."""

from datetime import datetime
from typing import Optional

from sqlmodel import Field, Relationship, SQLModel

from app.domains.market.models import Ticker


class AIAnalysis(SQLModel, table=True):
    """Cached AI narrative analysis per ticker and mode."""

    __tablename__ = "ia_analyses"

    id: int | None = Field(default=None, primary_key=True)
    ticker_id: int | None = Field(default=None, foreign_key="tickers.id", index=True)
    mode: str = Field(max_length=30, index=True)  # 'iq_score', 'bpf', 'recommandation'...
    model: str | None = Field(default=None, max_length=50)
    prompt_hash: str | None = Field(default=None, max_length=64, index=True)
    response: str | None = None
    tokens_in: int | None = None
    tokens_out: int | None = None
    cached: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    ticker: Optional[Ticker] = Relationship()


class CacheKV(SQLModel, table=True):
    """Generic key-value cache with TTL (fallback if Redis unavailable)."""

    __tablename__ = "cache_kv"

    key: str = Field(primary_key=True, max_length=255)
    value: bytes | None = None
    expires_at: datetime | None = Field(default=None, index=True)
