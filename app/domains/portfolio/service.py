"""CasaQuant Unified — Portfolio service layer.

Portfolio valuation, KPIs, position management. Async-first.
"""

from datetime import date
from decimal import Decimal
from typing import Any

from sqlmodel import select

from app.domains.portfolio.finance import recalculer_cmp, calculer_pnl_latent
from app.domains.portfolio.models import PortfolioPosition
from app.domains.portfolio.repository import PortfolioRepository


class PortfolioService:
    def __init__(self, repo: PortfolioRepository):
        self.repo = repo

    async def get_cash(self) -> float:
        """Cash = sum(virements) - sum(ACHAT montant_net) + sum(VENTE montant_encaisse)."""
        total_virements = await self.repo.get_virement_total()
        summary = await self.repo.get_transaction_summary()
        return round(total_virements - summary["total_achats_net"] + summary["total_ventes_encaissees"], 2)

    async def get_positions_with_cmp(self) -> dict[int, dict]:
        """Recalculate CMP from all transactions."""
        txs = await self.repo.list_transactions()
        tx_dicts = [
            {
                "ticker_id": t.ticker_id,
                "type": t.type,
                "quantite": t.qty,
                "montant_net": float(t.montant_net) if t.montant_net else 0.0,
            }
            for t in txs
        ]
        return recalculer_cmp(tx_dicts)

    async def build_portfolio(self, last_prices: dict[int, float]) -> dict[str, Any]:
        """Full portfolio with positions + KPIs.

        Args:
            last_prices: dict {ticker_id: latest_close_price}
        """
        positions = await self.get_positions_with_cmp()
        cash = await self.get_cash()
        summary = await self.repo.get_transaction_summary()

        active = {
            tid: pos for tid, pos in positions.items()
            if pos["quantite"] > 0
        }

        lignes = []
        valeur_portefeuille = 0.0
        pnl_latent_total = 0.0
        cout_total = 0.0

        for tid, pos in active.items():
            prix = last_prices.get(tid)
            if not prix:
                continue
            pnl = calculer_pnl_latent(pos["quantite"], pos["cmp"], prix)
            valeur_portefeuille += pnl["valeur_marche"]
            pnl_latent_total += pnl["pnl_brut"]
            cout_total += pnl["cout_position"]
            lignes.append({
                "ticker_id": tid,
                "quantite": pos["quantite"],
                "cmp": pos["cmp"],
                "prix_actuel": prix,
                **pnl,
                "poids_pct": None,
            })

        for l in lignes:
            l["poids_pct"] = round(l["valeur_marche"] / valeur_portefeuille * 100, 2) if valeur_portefeuille > 0 else 0.0

        valorisation_totale = round(valeur_portefeuille + cash, 2)
        total_virements = await self.repo.get_virement_total()
        perf_globale = round((valorisation_totale - total_virements) / total_virements * 100, 2) if total_virements > 0 else 0.0

        return {
            "positions": sorted(lignes, key=lambda x: -x["valeur_marche"]),
            "kpis": {
                "valorisation_portefeuille": round(valeur_portefeuille, 2),
                "cash_dispo": round(cash, 2),
                "valorisation_totale": valorisation_totale,
                "cout_total": round(cout_total, 2),
                "pnl_latent": round(pnl_latent_total, 2),
                "pnl_latent_pct": round(pnl_latent_total / cout_total * 100, 2) if cout_total > 0 else 0.0,
                "pnl_realise": round(summary["pnl_realise"], 2),
                "pnl_total": round(pnl_latent_total + summary["pnl_realise"], 2),
                "total_virements": round(total_virements, 2),
                "perf_globale_pct": perf_globale,
                "nb_positions": len(lignes),
            },
        }

    async def sync_positions(self) -> None:
        """Sync portfolio_positions table from transaction-derived CMP.
        Idempotent — can be called after any transaction write."""
        positions = await self.get_positions_with_cmp()
        for tid, pos in positions.items():
            if pos["quantite"] > 0:
                await self.repo.upsert_position(
                    PortfolioPosition(
                        ticker_id=tid,
                        qty=pos["quantite"],
                        avg_price=Decimal(str(pos["cmp"])),
                        opened_at=date.today(),
                    )
                )
            else:
                # Close position if qty == 0
                result = await self.repo.session.exec(
                    select(PortfolioPosition).where(PortfolioPosition.ticker_id == tid)
                )
                existing = result.first()
                if existing:
                    existing.qty = 0
                    self.repo.session.add(existing)
                    await self.repo.session.commit()
