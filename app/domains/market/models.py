"""CasaQuant Unified — Market data models (intraday + EOD)."""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlmodel import Field, Relationship, SQLModel


class Ticker(SQLModel, table=True):
    """BVC ticker master data."""

    __tablename__ = "tickers"

    id: int | None = Field(default=None, primary_key=True)
    code_bc: str = Field(index=True, unique=True, max_length=20)
    nom: str = Field(max_length=200)
    secteur: str | None = Field(default=None, max_length=100)
    actif: bool = Field(default=True)
    illiquide: bool = Field(default=False)

    # Relationships
    ohlcv: list["OHLCV"] = Relationship(back_populates="ticker")
    indicators: Optional["IndicatorsSnapshot"] = Relationship(back_populates="ticker")
    scoring: Optional["ScoringFinal"] = Relationship(back_populates="ticker")  # type: ignore[name-defined]


class MarketSnapshot(SQLModel, table=True):
    """Intraday snapshot (ex INTRADAY_BD.snapshots)."""

    __tablename__ = "market_snapshots"

    id: int | None = Field(default=None, primary_key=True)
    ticker_id: int = Field(foreign_key="tickers.id", index=True)
    session_time: datetime = Field(index=True)
    price: Decimal | None = Field(default=None, max_digits=12, decimal_places=4)
    volume: int | None = Field(default=None)
    bid: Decimal | None = Field(default=None, max_digits=12, decimal_places=4)
    ask: Decimal | None = Field(default=None, max_digits=12, decimal_places=4)
    source: str | None = Field(default=None, max_length=50)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class MarketFeature(SQLModel, table=True):
    """Aggregated daily features (ex INTRADAY_BD.features)."""

    __tablename__ = "market_features"

    id: int | None = Field(default=None, primary_key=True)
    ticker_id: int = Field(foreign_key="tickers.id", index=True)
    date: date = Field(index=True)
    open: Decimal | None = Field(default=None, max_digits=12, decimal_places=4)
    high: Decimal | None = Field(default=None, max_digits=12, decimal_places=4)
    low: Decimal | None = Field(default=None, max_digits=12, decimal_places=4)
    close: Decimal | None = Field(default=None, max_digits=12, decimal_places=4)
    volume: int | None = Field(default=None)
    vwap: Decimal | None = Field(default=None, max_digits=12, decimal_places=4)

    class Config:
        # Ensure uniqueness ticker + date
        pass


class OHLCV(SQLModel, table=True):
    """End-of-day OHLCV (ex casaquant_xai.ohlcv)."""

    __tablename__ = "ohlcv"

    id: int | None = Field(default=None, primary_key=True)
    ticker_id: int = Field(foreign_key="tickers.id", index=True)
    date: date = Field(index=True)
    open: Decimal | None = Field(default=None, max_digits=12, decimal_places=4)
    high: Decimal | None = Field(default=None, max_digits=12, decimal_places=4)
    low: Decimal | None = Field(default=None, max_digits=12, decimal_places=4)
    close: Decimal | None = Field(default=None, max_digits=12, decimal_places=4)
    volume: int | None = Field(default=None)

    ticker: Ticker = Relationship(back_populates="ohlcv")

    class Config:
        pass


class IndicatorsSnapshot(SQLModel, table=True):
    """Latest computed technical indicators per ticker."""

    __tablename__ = "indicators_snapshot"

    ticker_id: int = Field(foreign_key="tickers.id", primary_key=True)
    computed_at: datetime | None = Field(default_factory=datetime.utcnow)
    sma20: Decimal | None = Field(default=None, max_digits=12, decimal_places=4)
    sma50: Decimal | None = Field(default=None, max_digits=12, decimal_places=4)
    sma200: Decimal | None = Field(default=None, max_digits=12, decimal_places=4)
    rsi: Decimal | None = Field(default=None, max_digits=5, decimal_places=2)
    macd: Decimal | None = Field(default=None, max_digits=12, decimal_places=4)
    bb_pct: Decimal | None = Field(default=None, max_digits=5, decimal_places=4)
    adx: Decimal | None = Field(default=None, max_digits=5, decimal_places=2)
    atr: Decimal | None = Field(default=None, max_digits=12, decimal_places=4)

    ticker: Ticker = Relationship(back_populates="indicators")


class MASIIndex(SQLModel, table=True):
    """MASI daily index values."""

    __tablename__ = "masi_index"

    id: int | None = Field(default=None, primary_key=True)
    date: date = Field(index=True, unique=True)
    open: Decimal | None = Field(default=None, max_digits=12, decimal_places=4)
    high: Decimal | None = Field(default=None, max_digits=12, decimal_places=4)
    low: Decimal | None = Field(default=None, max_digits=12, decimal_places=4)
    close: Decimal | None = Field(default=None, max_digits=12, decimal_places=4)
    volume: int | None = Field(default=None)
