"""CasaQuant Unified — Backtest models (V4 + V7 strategies)."""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlmodel import Field, Relationship, SQLModel

from app.domains.market.models import Ticker


class BacktestResult(SQLModel, table=True):
    """Summary of a strategy backtest run per ticker."""

    __tablename__ = "backtest_results"

    id: int | None = Field(default=None, primary_key=True)
    ticker_id: int = Field(foreign_key="tickers.id", index=True)
    strategy_version: str = Field(max_length=10, index=True)  # 'v4', 'v7'
    win_rate: Decimal | None = Field(default=None, max_digits=5, decimal_places=2)
    profit_val: Decimal | None = Field(default=None, max_digits=15, decimal_places=2)
    max_drawdown: Decimal | None = Field(default=None, max_digits=5, decimal_places=2)
    sharpe: Decimal | None = Field(default=None, max_digits=5, decimal_places=2)
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    params_hash: str | None = Field(default=None, max_length=64)
    computed_at: datetime = Field(default_factory=datetime.utcnow)

    ticker: Optional[Ticker] = Relationship()
    trades: list["BacktestTrade"] = Relationship(back_populates="result")


class BacktestTrade(SQLModel, table=True):
    """Individual trades from a backtest run."""

    __tablename__ = "backtest_trades"

    id: int | None = Field(default=None, primary_key=True)
    result_id: int = Field(foreign_key="backtest_results.id", index=True)
    entry_date: Optional[date] = None
    exit_date: Optional[date] = None
    entry_price: Decimal | None = Field(default=None, max_digits=12, decimal_places=4)
    exit_price: Decimal | None = Field(default=None, max_digits=12, decimal_places=4)
    qty: int | None = None
    pnl: Decimal | None = Field(default=None, max_digits=15, decimal_places=2)
    fees: Decimal | None = Field(default=None, max_digits=15, decimal_places=2)
    exit_reason: str | None = Field(default=None, max_length=20)

    result: BacktestResult = Relationship(back_populates="trades")


class BacktestLabRun(SQLModel, table=True):
    """Research lab backtest experiments (V5/V6)."""

    __tablename__ = "backtest_lab_runs"

    id: int | None = Field(default=None, primary_key=True)
    strategy_version: str = Field(max_length=10)
    description: str | None = None
    params: str | None = None  # JSON string
    win_rate: Decimal | None = Field(default=None, max_digits=5, decimal_places=2)
    profit_val: Decimal | None = Field(default=None, max_digits=15, decimal_places=2)
    max_drawdown: Decimal | None = Field(default=None, max_digits=5, decimal_places=2)
    computed_at: datetime = Field(default_factory=datetime.utcnow)
