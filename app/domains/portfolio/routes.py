"""CasaQuant Unified — Portfolio API routes.

Real portfolio + transactions + virements. Async-first.
"""

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlmodel import select

from app.dependencies import DBDep
from app.domains.market.models import Ticker
from app.domains.portfolio.finance import calculer_achat, calculer_vente, recalculer_cmp
from app.domains.portfolio.models import Transaction, Virement
from app.domains.portfolio.repository import PortfolioRepository
from app.domains.portfolio.service import PortfolioService

router = APIRouter(prefix="/api/portfolio", tags=["Portfolio"])
transactions_router = APIRouter(prefix="/api/transactions", tags=["Écriture — Transactions"])
virements_router = APIRouter(prefix="/api/virements", tags=["Écriture — Virements"])


# ── Pydantic schemas ──────────────────────────────────────────────

class TransactionIn(BaseModel):
    ticker_id: int = Field(..., gt=0)
    type: str = Field(..., pattern=r"^(ACHAT|VENTE)$")
    date: str = Field(..., description="YYYY-MM-DD")
    quantite: int = Field(..., gt=0)
    prix_unitaire: Decimal = Field(..., gt=0)

    @field_validator("date")
    @classmethod
    def _check_date(cls, v: str) -> str:
        date.fromisoformat(v)
        return v


class VirementIn(BaseModel):
    date: str = Field(..., description="YYYY-MM-DD")
    designation: str = Field(..., min_length=1)
    montant: Decimal
    type: str = Field(default="DEPOT", pattern=r"^(DEPOT|RETRAIT)$")

    @field_validator("date")
    @classmethod
    def _check_date(cls, v: str) -> str:
        date.fromisoformat(v)
        return v


# ── Helpers ─────────────────────────────────────────────────────

def _repo(db) -> PortfolioRepository:
    return PortfolioRepository(db)


def _service(db) -> PortfolioService:
    return PortfolioService(_repo(db))


# ── Portfolio ───────────────────────────────────────────────────

@router.get("")
async def get_portfolio(db: DBDep) -> dict[str, Any]:
    """Full portfolio: active positions + KPIs + cash."""
    svc = _service(db)
    positions = await svc.get_positions_with_cmp()
    cash = await svc.get_cash()
    return {
        "positions": {
            tid: {"quantite": p["quantite"], "cmp": p["cmp"], "cout_total": p["cout_total"]}
            for tid, p in positions.items() if p["quantite"] > 0
        },
        "cash_dispo": cash,
        "note": "Prices required for full valuation — wire market data endpoint",
    }


@router.get("/kpis")
async def get_kpis(db: DBDep) -> dict[str, Any]:
    """Portfolio KPIs summary (without position detail)."""
    svc = _service(db)
    positions = await svc.get_positions_with_cmp()
    cash = await svc.get_cash()
    summary = await _repo(db).get_transaction_summary()
    total_virements = await _repo(db).get_virement_total()
    valorisation_totale = cash + sum(p["cout_total"] for p in positions.values())
    perf = round((valorisation_totale - total_virements) / total_virements * 100, 2) if total_virements > 0 else 0.0
    return {
        "cash_dispo": cash,
        "nb_positions": sum(1 for p in positions.values() if p["quantite"] > 0),
        "pnl_realise": round(summary["pnl_realise"], 2),
        "total_virements": round(total_virements, 2),
        "perf_globale_pct": perf,
    }


@router.get("/snapshots")
async def get_snapshots(
    db: DBDep,
    days: int = Query(default=90, ge=7, le=365),
) -> dict[str, Any]:
    """Daily NAV snapshot history."""
    repo = _repo(db)
    since = date.today() - timedelta(days=days)
    rows = await repo.list_snapshots(since=since)
    snapshots = [
        {
            "date": str(r.date),
            "valorisation": float(r.valorisation),
            "cash": float(r.cash),
            "nb_positions": r.nb_positions,
            "perf_jour_pct": float(r.perf_jour_pct) if r.perf_jour_pct else None,
            "perf_masi_pct": float(r.perf_masi_pct) if r.perf_masi_pct else None,
        }
        for r in rows
    ]
    resume = None
    if snapshots:
        first = snapshots[0]["valorisation"]
        last = snapshots[-1]["valorisation"]
        perf_totale = round((last - first) / first * 100, 2) if first > 0 else None
        resume = {"valorisation_actuelle": last, "perf_totale_pct": perf_totale}
    return {"snapshots": snapshots, "resume": resume}


# ── Transactions ────────────────────────────────────────────────

@transactions_router.get("")
async def get_transactions(
    db: DBDep,
    ticker_id: int | None = None,
    type: str | None = None,
) -> list[dict[str, Any]]:
    """List transactions with optional filters."""
    repo = _repo(db)
    rows = await repo.list_transactions(ticker_id=ticker_id, tx_type=type)
    return [
        {
            "id": r.id,
            "ticker_id": r.ticker_id,
            "date": str(r.date),
            "type": r.type,
            "quantite": r.qty,
            "prix_unitaire": float(r.price),
            "montant_net": float(r.montant_net) if r.montant_net else None,
            "montant_encaisse": float(r.montant_encaisse) if r.montant_encaisse else None,
            "profit_net": float(r.profit_net) if r.profit_net else None,
        }
        for r in rows
    ]


@transactions_router.post("", status_code=201)
async def post_transaction(db: DBDep, tx_in: TransactionIn) -> dict[str, Any]:
    """Record a buy or sell with automatic BVC fee calculation."""
    repo = _repo(db)

    # Verify ticker exists
    result = await db.exec(select(Ticker).where(Ticker.id == tx_in.ticker_id))
    ticker = result.first()
    if not ticker:
        raise HTTPException(status_code=404, detail=f"Ticker ID {tx_in.ticker_id} not found")

    if tx_in.type == "ACHAT":
        result = calculer_achat(tx_in.quantite, float(tx_in.prix_unitaire))
        tx = Transaction(
            ticker_id=tx_in.ticker_id,
            date=date.fromisoformat(tx_in.date),
            type="ACHAT",
            qty=tx_in.quantite,
            price=Decimal(str(tx_in.prix_unitaire)),
            brokerage=Decimal(str(result.frais.commission_courtage)),
            tax=Decimal(str(result.frais.impot_bourse)),
            vat=Decimal(str(result.frais.tva)),
            total=Decimal(str(result.frais.total_frais)),
            montant_net=Decimal(str(result.montant_net)),
            impot_pv=Decimal("0"),
        )
    else:  # VENTE
        txs = await repo.list_transactions()
        tx_dicts = [
            {
                "ticker_id": t.ticker_id,
                "type": t.type,
                "quantite": t.qty,
                "montant_net": float(t.montant_net) if t.montant_net else 0.0,
            }
            for t in txs
        ]
        positions = recalculer_cmp(tx_dicts)
        pos = positions.get(tx_in.ticker_id, {})
        cmp = pos.get("cmp", 0.0)
        qte_dispo = pos.get("quantite", 0)

        if tx_in.quantite > qte_dispo:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient quantity: {qte_dispo} available, {tx_in.quantite} requested",
            )

        result = calculer_vente(tx_in.quantite, float(tx_in.prix_unitaire), cmp)
        tx = Transaction(
            ticker_id=tx_in.ticker_id,
            date=date.fromisoformat(tx_in.date),
            type="VENTE",
            qty=tx_in.quantite,
            price=Decimal(str(tx_in.prix_unitaire)),
            brokerage=Decimal(str(result.frais.commission_courtage)),
            tax=Decimal(str(result.frais.impot_bourse)),
            vat=Decimal(str(result.frais.tva)),
            total=Decimal(str(result.frais.total_frais)),
            cmp_moment=Decimal(str(cmp)),
            plus_value_brute=Decimal(str(result.plus_value_brute)),
            impot_pv=Decimal(str(result.impot_pv)),
            profit_net=Decimal(str(result.profit_net)),
            montant_encaisse=Decimal(str(result.montant_encaisse)),
            montant_net=Decimal(str(result.montant_net)),
        )

    await repo.create_transaction(tx)
    # Sync positions table
    await _service(db).sync_positions()

    return {
        "id": tx.id,
        "type": tx_in.type,
        "montant_net": result.montant_net,
        "frais": {
            "commission_courtage": result.frais.commission_courtage,
            "impot_bourse": result.frais.impot_bourse,
            "tva": result.frais.tva,
            "total_frais": result.frais.total_frais,
        },
    }


# ── Virements ───────────────────────────────────────────────────

@virements_router.get("")
async def get_virements(db: DBDep) -> dict[str, Any]:
    """List all cash movements."""
    repo = _repo(db)
    rows = await repo.list_virements()
    total = sum(float(r.amount) for r in rows)
    return {
        "total_mad": round(total, 2),
        "virements": [
            {"id": r.id, "date": str(r.date), "type": r.type, "montant": float(r.amount), "designation": r.description}
            for r in rows
        ],
    }


@virements_router.post("", status_code=201)
async def post_virement(db: DBDep, v_in: VirementIn) -> dict[str, Any]:
    """Record a deposit or withdrawal."""
    repo = _repo(db)
    v = Virement(
        date=date.fromisoformat(v_in.date),
        type=v_in.type,
        amount=Decimal(str(v_in.montant)),
        description=v_in.designation,
    )
    await repo.create_virement(v)
    return {"id": v.id, "montant": float(v_in.montant), "designation": v_in.designation}
