"""CasaQuant Unified — Scoring models (5-pillar multi-criteria)."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlmodel import Field, Relationship, SQLModel

from app.domains.market.models import Ticker


class ScoringFinal(SQLModel, table=True):
    """Latest computed 5-pillar score per ticker."""

    __tablename__ = "scoring_final"

    ticker_id: int = Field(foreign_key="tickers.id", primary_key=True)
    score_momentum: Decimal | None = Field(default=None, max_digits=5, decimal_places=2)
    score_trend: Decimal | None = Field(default=None, max_digits=5, decimal_places=2)
    score_risk: Decimal | None = Field(default=None, max_digits=5, decimal_places=2)
    score_value: Decimal | None = Field(default=None, max_digits=5, decimal_places=2)
    score_liquidity: Decimal | None = Field(default=None, max_digits=5, decimal_places=2)
    score_final: Decimal | None = Field(default=None, max_digits=5, decimal_places=2)
    computed_at: datetime | None = Field(default_factory=datetime.utcnow)

    ticker: Optional[Ticker] = Relationship(back_populates="scoring")


class ScoringHistory(SQLModel, table=True):
    """Historical scoring snapshots for trend analysis."""

    __tablename__ = "scoring_history"

    id: int | None = Field(default=None, primary_key=True)
    ticker_id: int = Field(foreign_key="tickers.id", index=True)
    date: date = Field(index=True)  # type: ignore[name-defined]
    score_momentum: Decimal | None = Field(default=None, max_digits=5, decimal_places=2)
    score_trend: Decimal | None = Field(default=None, max_digits=5, decimal_places=2)
    score_risk: Decimal | None = Field(default=None, max_digits=5, decimal_places=2)
    score_value: Decimal | None = Field(default=None, max_digits=5, decimal_places=2)
    score_liquidity: Decimal | None = Field(default=None, max_digits=5, decimal_places=2)
    score_final: Decimal | None = Field(default=None, max_digits=5, decimal_places=2)
    computed_at: datetime = Field(default_factory=datetime.utcnow)
