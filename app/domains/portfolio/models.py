"""CasaQuant Unified — Portfolio domain models (SQLModel)."""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlmodel import Field, SQLModel


class Transaction(SQLModel, table=True):
    """Real buy/sell transaction with full BVC fee breakdown."""

    __tablename__ = "transactions"

    id: Optional[int] = Field(default=None, primary_key=True)
    ticker_id: int = Field(foreign_key="tickers.id")
    date: date
    type: str = Field(max_length=10)  # ACHAT | VENTE
    qty: int = Field(default=0)
    price: Decimal = Field(max_digits=12, decimal_places=4)
    brokerage: Decimal = Field(max_digits=15, decimal_places=2)
    tax: Decimal = Field(max_digits=15, decimal_places=2)
    vat: Decimal = Field(max_digits=15, decimal_places=2)
    total: Decimal = Field(max_digits=15, decimal_places=2)

    # Extended fields (not in original 001_init_schema.sql, added via migration)
    cmp_moment: Optional[Decimal] = Field(default=None, max_digits=12, decimal_places=4)
    plus_value_brute: Optional[Decimal] = Field(default=None, max_digits=15, decimal_places=2)
    impot_pv: Optional[Decimal] = Field(default=None, max_digits=15, decimal_places=2)
    profit_net: Optional[Decimal] = Field(default=None, max_digits=15, decimal_places=2)
    montant_encaisse: Optional[Decimal] = Field(default=None, max_digits=15, decimal_places=2)

    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)


class Virement(SQLModel, table=True):
    """Cash deposit or withdrawal."""

    __tablename__ = "virements"

    id: Optional[int] = Field(default=None, primary_key=True)
    date: date
    type: str = Field(max_length=20)  # DEPOT | RETRAIT
    amount: Decimal = Field(max_digits=15, decimal_places=2)
    description: Optional[str] = None
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)


class PortfolioPosition(SQLModel, table=True):
    """Active position snapshot (derived from transactions, not source of truth)."""

    __tablename__ = "portfolio_positions"

    id: Optional[int] = Field(default=None, primary_key=True)
    ticker_id: int = Field(foreign_key="tickers.id", unique=True)
    qty: int = Field(default=0)
    avg_price: Optional[Decimal] = Field(default=None, max_digits=12, decimal_places=4)
    opened_at: Optional[date] = None
    strategy: str = Field(default="v4", max_length=10)
    updated_at: Optional[datetime] = Field(default_factory=datetime.utcnow)


class PaperTrade(SQLModel, table=True):
    """Simulated trade (isolated from real portfolio)."""

    __tablename__ = "paper_trades"

    id: Optional[int] = Field(default=None, primary_key=True)
    ticker_id: int = Field(foreign_key="tickers.id")
    type: str = Field(max_length=10)  # ACHAT | VENTE
    qty: int = Field(default=0)
    price: Optional[Decimal] = Field(default=None, max_digits=12, decimal_places=4)
    status: str = Field(default="OPEN", max_length=20)  # OPEN | CLOSED
    pnl: Optional[Decimal] = Field(default=None, max_digits=15, decimal_places=2)
    opened_at: Optional[date] = None
    closed_at: Optional[date] = None
    strategy: str = Field(default="v4", max_length=10)
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)


class PortfolioSnapshot(SQLModel, table=True):
    """Daily NAV snapshot vs MASI."""

    __tablename__ = "portfolio_snapshots"

    id: Optional[int] = Field(default=None, primary_key=True)
    date: date = Field(unique=True)
    valorisation: Decimal = Field(max_digits=15, decimal_places=2)
    cash: Decimal = Field(max_digits=15, decimal_places=2)
    nb_positions: int = Field(default=0)
    perf_jour_pct: Optional[Decimal] = Field(default=None, max_digits=5, decimal_places=2)
    perf_masi_pct: Optional[Decimal] = Field(default=None, max_digits=5, decimal_places=2)
    created_at: Optional[datetime] = Field(default_factory=datetime.utcnow)
