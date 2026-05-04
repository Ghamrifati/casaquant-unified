"""CasaQuant Unified — Portfolio financial calculations.

CMP CDVM (gliding weighted average cost), buy/sell with BVC fees,
realized & unrealized P&L.

All monetary math uses Decimal internally, float externally.
"""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP


_Q4 = Decimal("0.0001")
_Q2 = Decimal("0.01")

# Fee rates (mirror of app.domains.common.fees + capital gains tax)
TAUX_COURTAGE = Decimal("0.006")
MIN_COURTAGE = Decimal("10.0")
TAUX_IMPOT_BOURSE = Decimal("0.001")
TAUX_TVA = Decimal("0.10")
TAUX_IMPOT_PV = Decimal("0.15")


def _to_dec(value: float | int | Decimal) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def _q4(value: Decimal) -> Decimal:
    return value.quantize(_Q4, rounding=ROUND_HALF_UP)


def _q2(value: Decimal) -> Decimal:
    return value.quantize(_Q2, rounding=ROUND_HALF_UP)


def _f4(value: Decimal) -> float:
    return float(_q4(value))


def _f2(value: Decimal) -> float:
    return float(_q2(value))


@dataclass(frozen=True)
class FraisBVC:
    commission_courtage: float
    impot_bourse: float
    tva: float
    total_frais: float


@dataclass(frozen=True)
class ResultatTransaction:
    prix_brut: float
    frais: FraisBVC
    montant_net: float          # Achat: brut + frais | Vente: brut - frais
    plus_value_brute: float     # 0 si achat, (pv - cmp) * qte si vente
    impot_pv: float             # 0 si achat ou PV <= 0
    profit_net: float           # 0 si achat, sinon PV brute - impôt PV
    montant_encaisse: float     # 0 si achat, sinon brut - frais - impôt PV


def calculer_frais_decimal(montant_brut: Decimal) -> FraisBVC:
    commission_courtage = max(montant_brut * TAUX_COURTAGE, MIN_COURTAGE)
    impot_bourse = montant_brut * TAUX_IMPOT_BOURSE
    tva = commission_courtage * TAUX_TVA
    total_frais = commission_courtage + impot_bourse + tva
    return FraisBVC(
        commission_courtage=_f4(commission_courtage),
        impot_bourse=_f4(impot_bourse),
        tva=_f4(tva),
        total_frais=_f4(total_frais),
    )


def calculer_achat(quantite: int, prix_unitaire: float) -> ResultatTransaction:
    """Calculate net cost of a buy (gross + fees)."""
    qte = _to_dec(quantite)
    pu = _to_dec(prix_unitaire)
    prix_brut_dec = _q4(qte * pu)
    frais = calculer_frais_decimal(prix_brut_dec)
    montant_net_dec = _q4(prix_brut_dec + _to_dec(frais.total_frais))
    return ResultatTransaction(
        prix_brut=float(prix_brut_dec),
        frais=frais,
        montant_net=float(montant_net_dec),
        plus_value_brute=0.0,
        impot_pv=0.0,
        profit_net=0.0,
        montant_encaisse=0.0,
    )


def calculer_vente(quantite: int, prix_unitaire: float, cmp: float) -> ResultatTransaction:
    """Calculate proceeds from a sell (gross - fees - capital gains tax)."""
    qte = _to_dec(quantite)
    pu = _to_dec(prix_unitaire)
    cmp_dec = _to_dec(cmp)
    prix_brut_dec = _q4(qte * pu)
    frais = calculer_frais_decimal(prix_brut_dec)
    plus_value_brute_dec = _q4((pu - cmp_dec) * qte)
    impot_pv_dec = (
        _q4(plus_value_brute_dec * TAUX_IMPOT_PV)
        if plus_value_brute_dec > 0
        else Decimal("0")
    )
    profit_net_dec = (
        _q4(plus_value_brute_dec - impot_pv_dec)
        if plus_value_brute_dec > 0
        else plus_value_brute_dec
    )
    montant_encaisse_dec = _q4(prix_brut_dec - _to_dec(frais.total_frais) - impot_pv_dec)
    montant_net_dec = _q4(prix_brut_dec - _to_dec(frais.total_frais))
    return ResultatTransaction(
        prix_brut=float(prix_brut_dec),
        frais=frais,
        montant_net=float(montant_net_dec),
        plus_value_brute=float(plus_value_brute_dec),
        impot_pv=float(impot_pv_dec),
        profit_net=float(profit_net_dec),
        montant_encaisse=float(montant_encaisse_dec),
    )


def recalculer_cmp(transactions_triees: list[dict]) -> dict[int, dict]:
    """Recalculate CDVM CMP for each ticker from chronological transactions.

    CDVM method: CMP = (old_CMP * old_qty + new_total_cost) / new_qty
    Sales do NOT change the CMP.

    Args:
        transactions_triees: list of dicts with keys:
            ticker_id, type ('ACHAT'/'VENTE'), quantite, montant_net

    Returns:
        dict {ticker_id: {'cmp': float, 'quantite': int, 'cout_total': float}}
    """
    positions: dict[int, dict] = {}

    for tx in transactions_triees:
        tid = tx["ticker_id"]
        if tid not in positions:
            positions[tid] = {"cmp": 0.0, "quantite": 0, "cout_total": 0.0}

        pos = positions[tid]

        if tx["type"] == "ACHAT":
            ancien_cout = _to_dec(pos["cmp"]) * _to_dec(pos["quantite"])
            nouveau_cout = _to_dec(tx["montant_net"])
            nouvelle_qte = pos["quantite"] + tx["quantite"]
            pos["quantite"] = nouvelle_qte
            cout_total = _q4(ancien_cout + nouveau_cout)
            pos["cout_total"] = float(cout_total)
            pos["cmp"] = float(_q4(cout_total / _to_dec(nouvelle_qte))) if nouvelle_qte > 0 else 0.0

        elif tx["type"] == "VENTE":
            qte_vendue = tx["quantite"]
            qte_restante = max(pos["quantite"] - qte_vendue, 0)
            pos["cout_total"] = float(_q4(_to_dec(pos["cmp"]) * _to_dec(qte_restante)))
            pos["quantite"] = qte_restante
            # CMP unchanged after sale

    return positions


def calculer_pnl_latent(quantite: int, cmp: float, prix_actuel: float) -> dict:
    """Calculate unrealized P&L for an open position."""
    qte = _to_dec(quantite)
    valeur_marche_dec = _q2(qte * _to_dec(prix_actuel))
    cout_position_dec = _q2(qte * _to_dec(cmp))
    pnl_brut_dec = _q2(valeur_marche_dec - cout_position_dec)
    pnl_pct_dec = (
        _q2((pnl_brut_dec / cout_position_dec) * Decimal("100"))
        if cout_position_dec > 0
        else Decimal("0")
    )
    return {
        "valeur_marche": float(valeur_marche_dec),
        "cout_position": float(cout_position_dec),
        "pnl_brut": float(pnl_brut_dec),
        "pnl_pct": float(pnl_pct_dec),
    }
