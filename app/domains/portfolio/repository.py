"""CasaQuant Unified — Portfolio repository layer.

Bulk queries, no N+1. Async-first.
"""

from datetime import date
from typing import Sequence

from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, func

from app.domains.portfolio.models import Transaction, Virement, PortfolioPosition, PortfolioSnapshot


class PortfolioRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ── Transactions ──────────────────────────────────────────────

    async def list_transactions(
        self,
        ticker_id: int | None = None,
        tx_type: str | None = None,
    ) -> Sequence[Transaction]:
        stmt = select(Transaction).order_by(Transaction.date.asc(), Transaction.id.asc())
        if ticker_id is not None:
            stmt = stmt.where(Transaction.ticker_id == ticker_id)
        if tx_type is not None:
            stmt = stmt.where(Transaction.type == tx_type.upper())
        result = await self.session.exec(stmt)
        return result.all()

    async def create_transaction(self, tx: Transaction) -> Transaction:
        self.session.add(tx)
        await self.session.commit()
        await self.session.refresh(tx)
        return tx

    async def get_transaction_summary(self) -> dict:
        """Return totals for cash calculation."""
        achats = await self.session.exec(
            select(func.coalesce(func.sum(Transaction.montant_net), 0)).where(
                Transaction.type == "ACHAT"
            )
        )
        ventes = await self.session.exec(
            select(func.coalesce(func.sum(Transaction.montant_encaisse), 0)).where(
                Transaction.type == "VENTE"
            )
        )
        pv = await self.session.exec(
            select(func.coalesce(func.sum(Transaction.profit_net), 0)).where(
                Transaction.type == "VENTE"
            )
        )
        return {
            "total_achats_net": float(achats.one()),
            "total_ventes_encaissees": float(ventes.one()),
            "pnl_realise": float(pv.one()),
        }

    # ── Virements ───────────────────────────────────────────────────

    async def list_virements(self) -> Sequence[Virement]:
        stmt = select(Virement).order_by(Virement.date.desc())
        result = await self.session.exec(stmt)
        return result.all()

    async def create_virement(self, v: Virement) -> Virement:
        self.session.add(v)
        await self.session.commit()
        await self.session.refresh(v)
        return v

    async def get_virement_total(self) -> float:
        total = await self.session.exec(
            select(func.coalesce(func.sum(Virement.amount), 0))
        )
        return float(total.one())

    # ── Positions ───────────────────────────────────────────────────

    async def get_positions(self) -> Sequence[PortfolioPosition]:
        stmt = select(PortfolioPosition).where(PortfolioPosition.qty > 0)
        result = await self.session.exec(stmt)
        return result.all()

    async def upsert_position(self, pos: PortfolioPosition) -> PortfolioPosition:
        result = await self.session.exec(
            select(PortfolioPosition).where(
                PortfolioPosition.ticker_id == pos.ticker_id
            )
        )
        existing = result.first()
        if existing:
            existing.qty = pos.qty
            existing.avg_price = pos.avg_price
            existing.opened_at = pos.opened_at
            existing.updated_at = pos.updated_at
            self.session.add(existing)
        else:
            self.session.add(pos)
        await self.session.commit()
        return existing or pos

    # ── Snapshots ───────────────────────────────────────────────────

    async def list_snapshots(self, since: date | None = None) -> Sequence[PortfolioSnapshot]:
        stmt = select(PortfolioSnapshot).order_by(PortfolioSnapshot.date.asc())
        if since is not None:
            stmt = stmt.where(PortfolioSnapshot.date >= since)
        result = await self.session.exec(stmt)
        return result.all()

    async def create_snapshot(self, snap: PortfolioSnapshot) -> PortfolioSnapshot:
        self.session.add(snap)
        await self.session.commit()
        await self.session.refresh(snap)
        return snap

    async def get_latest_snapshot(self) -> PortfolioSnapshot | None:
        stmt = (
            select(PortfolioSnapshot)
            .order_by(PortfolioSnapshot.date.desc())
            .limit(1)
        )
        result = await self.session.exec(stmt)
        return result.first()
