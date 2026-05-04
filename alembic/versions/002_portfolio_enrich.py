"""Enrich portfolio schema.

Revision ID: 002
Revises: 001
"""

from pathlib import Path

# revision identifiers, used by Alembic.
revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None

SQL_PATH = Path(__file__).with_suffix(".sql")


def upgrade() -> None:
    from alembic import op

    sql = SQL_PATH.read_text(encoding="utf-8")
    op.execute(sql)


def downgrade() -> None:
    from alembic import op

    op.execute(
        """
        ALTER TABLE transactions
            DROP COLUMN IF EXISTS cmp_moment,
            DROP COLUMN IF EXISTS plus_value_brute,
            DROP COLUMN IF EXISTS impot_pv,
            DROP COLUMN IF EXISTS profit_net,
            DROP COLUMN IF EXISTS montant_encaisse;
        DROP TABLE IF EXISTS portfolio_snapshots;
        """
    )
