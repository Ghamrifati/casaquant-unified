"""CasaQuant Unified — Portfolio, transactions, and paper trading models."""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlmodel import Field, Relationship, SQLModel

from app.domains.market.models import Ticker


class PortfolioPosition(SQLModel, table=True):
    """Active portfolio positions."""

    __tablename__ = "portfolio_positions"

    id: int | None = Field(default=None, primary_key=True)
    ticker_id: int = Field(foreign_key="tickers.id", index=True)
    qty: int = Field(default=0)
    avg_price: Decimal | None = Field(default=None, max_digits=12, decimal_places=4)
    opened_at: Optional[date] = None
    strategy: str = Field(default="v4", max_length=10)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    ticker: Optional[Ticker] = Relationship()


class Transaction(SQLModel, table=True):
    """Recorded buy/sell transactions with real BVC fees."""

    __tablename__ = "transactions"

    id: int | None = Field(default=None, primary_key=True)
    ticker_id: int = Field(foreign_key="tickers.id", index=True)
    date: Optional[date] = None
    type: str = Field(max_length=10)  # 'ACHAT' | 'VENTE'
    qty: int = Field(default=0)
    price: Decimal | None = Field(default=None, max_digits=12, decimal_places=4)
    brokerage: Decimal | None = Field(default=None, max_digits=15, decimal_places=2)
    tax: Decimal | None = Field(default=None, max_digits=15, decimal_places=2)
    vat: Decimal | None = Field(default=None, max_digits=15, decimal_places=2)
    total: Decimal | None = Field(default=None, max_digits=15, decimal_places=2)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    ticker: Optional[Ticker] = Relationship()


class Virement(SQLModel, table=True):
    """Cash transfers (deposits/withdrawals)."""

    __tablename__ = "virements"

    id: int | None = Field(default=None, primary_key=True)
    date: Optional[date] = None
    type: str = Field(max_length=20)  # 'DEPOT' | 'RETRAIT'
    amount: Decimal | None = Field(default=None, max_digits=15, decimal_places=2)
    description: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PaperTrade(SQLModel, table=True):
    """Paper trading simulated orders."""

    __tablename__ = "paper_trades"

    id: int | None = Field(default=None, primary_key=True)
    ticker_id: int = Field(foreign_key="tickers.id", index=True)
    type: str = Field(max_length=10)  # 'ACHAT' | 'VENTE'
    qty: int = Field(default=0)
    price: Decimal | None = Field(default=None, max_digits=12, decimal_places=4)
    status: str = Field(default="OPEN", max_length=20)  # 'OPEN' | 'CLOSED'
    pnl: Decimal | None = Field(default=None, max_digits=15, decimal_places=2)
    opened_at: Optional[date] = None
    closed_at: Optional[date] = None
    strategy: str = Field(default="v4", max_length=10)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    ticker: Optional[Ticker] = Relationship()


class Watchlist(SQLModel, table=True):
    """User watchlist."""

    __tablename__ = "watchlist"

    id: int | None = Field(default=None, primary_key=True)
    ticker_id: int = Field(foreign_key="tickers.id", index=True)
    note: str | None = None
    alert_price: Decimal | None = Field(default=None, max_digits=12, decimal_places=4)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    ticker: Optional[Ticker] = Relationship()


class AlertRule(SQLModel, table=True):
    """Alert configuration rules."""

    __tablename__ = "alert_rules"

    id: int | None = Field(default=None, primary_key=True)
    ticker_id: int | None = Field(default=None, foreign_key="tickers.id")
    condition: str = Field(max_length=100)  # e.g. 'price > 150.00'
    active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AlertEvent(SQLModel, table=True):
    """Triggered alert events."""

    __tablename__ = "alert_events"

    id: int | None = Field(default=None, primary_key=True)
    rule_id: int = Field(foreign_key="alert_rules.id", index=True)
    triggered_at: datetime = Field(default_factory=datetime.utcnow)
    value: Decimal | None = Field(default=None, max_digits=12, decimal_places=4)
    message: str | None = None
    sent: bool = Field(default=False)
