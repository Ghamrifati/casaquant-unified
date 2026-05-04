"""Initial schema migration.

Revision ID: 001
Revises:
Create Date: 2026-05-04 14:00:00.000000+00:00
"""
from pathlib import Path

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """Apply initial schema."""
    # Read and execute SQL file
    sql_path = Path(__file__).parent / "001_init_schema.sql"
    if sql_path.exists():
        op.execute(sql_path.read_text(encoding="utf-8"))
    else:
        raise FileNotFoundError(f"Migration SQL not found: {sql_path}")


def downgrade():
    """Drop all tables (destructive)."""
    tables = [
        "quality_report", "ingestion_log", "juste_valeur", "job_runs",
        "cache_kv", "ia_analyses", "alert_events", "alert_rules",
        "watchlist", "paper_trades", "virements", "transactions",
        "portfolio_positions", "backtest_lab_runs", "backtest_trades",
        "backtest_results", "scoring_history", "scoring_final",
        "masi_index", "indicators_snapshot", "ohlcv", "market_features",
        "market_snapshots", "tickers",
    ]
    for table in tables:
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
