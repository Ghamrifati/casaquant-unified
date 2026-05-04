"""CasaQuant Unified — V4.1 "Bon Père de Famille" backtest engine.

Value-investing with technical timing. Horizon 6-12 months.
Real BVC fees: brokerage 0.6%, tax 0.1%, VAT 10%.
"""

import logging
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import numpy as np
import pandas as pd

from app.domains.common.fees import calculate_fees

logger = logging.getLogger("casaquant.backtest.v4")

SLIPPAGE = 0.001  # 0.1% slippage


@dataclass
class V4Signal:
    ticker_id: int
    code_bc: str
    date: str
    close: float
    fair_value: float
    decote_pct: float
    rsi_14: float | None
    bb_pct: float | None
    per: float | None
    div_yield: float | None
    signal_type: str
    score_entree: float


@dataclass
class V4Trade:
    ticker_id: int
    code_bc: str
    date_achat: str
    date_vente: str
    prix_achat: float
    prix_vente: float
    quantite: int
    fair_value: float
    pv_nette: float
    impot_pv: float
    duree_jours: int
    signal_sortie: str


@dataclass
class V4BacktestResult:
    nb_trades: int
    nb_gagnants: int
    nb_perdants: int
    win_rate: float
    profit_factor: float
    total_pv_nette: float
    avg_pv_par_trade: float
    avg_duree_jours: float
    max_gain: float
    max_perte: float
    trades: list[V4Trade]
    equity_curve: list[dict]


def _load_params() -> dict:
    """Load V4.1 parameters."""
    # Hard-coded locked parameters (same as legacy strategy_params.json)
    return {
        "decote_min_pct": 15.0,
        "per_max": 18.0,
        "div_yield_min": 2.0,
        "volume_min": 1000,
        "rsi_entry_max": 40.0,
        "bb_entry_max": 0.30,
        "target_jv_pct": 0.95,
        "stop_loss_pct": 0.15,
        "duree_max_jours": 252,
        "rsi_exit_hard": 75.0,
        "rsi_exit_soft": 65.0,
        "cooldown_jours": 60,
        "position_size_pct": 0.15,
        "capital_initial": 10000.0,
        "secteurs_exclus": ("Mines", "Immobilier"),
    }


def filtrer_univers(
    df_tickers: pd.DataFrame,
    df_jv: pd.DataFrame,
    df_indicators: pd.DataFrame,
) -> list[dict]:
    """Filter tickers passing V4.1 fundamental criteria."""
    params = _load_params()
    candidats = []

    for _, t in df_tickers.iterrows():
        if not t.get("actif") or t.get("illiquide"):
            continue

        secteur = (t.get("secteur") or "").strip().lower()
        if secteur in {s.lower() for s in params["secteurs_exclus"]}:
            continue

        # Get latest JV
        jv_rows = df_jv[df_jv["ticker_id"] == t["id"]]
        if jv_rows.empty:
            continue
        jv_row = jv_rows.sort_values("date").iloc[-1]
        fv = jv_row.get("valeur")
        close = df_indicators[df_indicators["ticker_id"] == t["id"]].get("close")
        if close is None or pd.isna(close) or close <= 0:
            continue
        close = float(close)

        if not fv or fv <= 0:
            continue

        decote = (float(fv) - close) / close * 100
        if decote < params["decote_min_pct"]:
            continue

        per = jv_row.get("per")
        dy = jv_row.get("dividend_yield")
        if per is not None and per > params["per_max"]:
            continue
        if dy is not None and dy < params["div_yield_min"] / 100:
            continue

        # Timing
        ind_rows = df_indicators[df_indicators["ticker_id"] == t["id"]]
        rsi = ind_rows.get("rsi_14")
        bb = ind_rows.get("bb_pct")
        rsi_ok = rsi is not None and not pd.isna(rsi) and rsi <= params["rsi_entry_max"]
        bb_ok = bb is not None and not pd.isna(bb) and bb <= params["bb_entry_max"]
        if not (rsi_ok or bb_ok):
            continue

        candidats.append({
            "ticker_id": t["id"],
            "code_bc": t["code_bc"],
            "nom": t["nom"],
            "close": close,
            "fair_value": float(fv),
            "decote_pct": round(decote, 2),
            "per": per,
            "div_yield": dy,
            "rsi_14": rsi,
            "bb_pct": bb,
        })

    candidats.sort(key=lambda c: -c["decote_pct"])
    return candidats


def backtest_ticker(
    ticker_id: int,
    code_bc: str,
    df: pd.DataFrame,
    jv_series: dict[str, float],
    params: dict | None = None,
) -> V4BacktestResult:
    """Run V4.1 backtest on a single ticker."""
    if params is None:
        params = _load_params()

    if len(df) < 60 or "RSI_14" not in df.columns:
        return V4BacktestResult(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, [], [])

    trades: list[V4Trade] = []
    capital = float(params["capital_initial"])
    en_position = False
    last_vente_idx = -params["cooldown_jours"] - 1
    prix_achat = 0.0
    quantite = 0
    date_achat = None
    fv_at_entry = 0.0
    stop_price = 0.0
    decote_at_entry = 0.0

    jv_dates = sorted(jv_series.keys())

    def get_jv_at_date(d: str) -> float | None:
        best = None
        for jd in jv_dates:
            if jd <= d:
                best = jv_series[jd]
            else:
                break
        return best

    dates = df.index.to_list()
    close_values = df["close"].to_numpy()
    open_values = df["open"].to_numpy() if "open" in df.columns else close_values
    rsi_values = df["RSI_14"].to_numpy()
    bb_values = (
        df["BBP_20_2.0_2.0"].to_numpy()
        if "BBP_20_2.0_2.0" in df.columns
        else np.full(len(df), np.nan)
    )

    def _next_exec(i: int) -> tuple[int, pd.Timestamp, float]:
        if i + 1 < len(dates):
            exec_idx = i + 1
            exec_date = dates[exec_idx]
            exec_open = open_values[exec_idx]
            if exec_open is not None and not pd.isna(exec_open) and exec_open > 0:
                return exec_idx, exec_date, float(exec_open)
            next_close = close_values[exec_idx]
            if next_close is not None and not pd.isna(next_close) and next_close > 0:
                return exec_idx, exec_date, float(next_close)
        return i, dates[i], float(close_values[i])

    for i, date in enumerate(dates):
        close = close_values[i]
        if pd.isna(close) or close <= 0:
            continue

        date_str = str(date.date()) if hasattr(date, "date") else str(date)
        rsi = rsi_values[i]
        bb_pct = bb_values[i]

        if en_position:
            duree = (date - date_achat).days if date_achat else 0
            signal_sortie = None

            if close >= fv_at_entry * params["target_jv_pct"]:
                signal_sortie = "TARGET_JV"
            elif close <= stop_price:
                signal_sortie = "STOP_LOSS"
            elif duree >= params["duree_max_jours"]:
                signal_sortie = "DUREE_MAX"
            elif (
                rsi is not None
                and not pd.isna(rsi)
                and duree > 20
            ):
                if rsi >= params["rsi_exit_hard"]:
                    signal_sortie = "RSI_EXIT_HARD"
                elif rsi >= params["rsi_exit_soft"]:
                    decote_residuelle = (
                        (fv_at_entry - close) / fv_at_entry * 100 if fv_at_entry > 0 else 0
                    )
                    decote_recuperee_pct = (
                        (1 - decote_residuelle / decote_at_entry) * 100
                        if decote_at_entry > 0
                        else 100
                    )
                    if decote_recuperee_pct >= 50:
                        signal_sortie = "RSI_EXIT_SOFT"

            if signal_sortie:
                exec_idx, exec_date, exec_price = _next_exec(i)
                prix_vente = exec_price * (1 - SLIPPAGE)
                brut_vente = quantite * prix_vente
                fees = calculate_fees(brut_vente)
                pv_brute = (prix_vente - prix_achat) * quantite
                impot = pv_brute * 0.15 if pv_brute > 0 else 0.0
                pv_nette = pv_brute - impot - fees["total_fees"]
                capital += brut_vente - fees["total_fees"] - impot
                duree_exec = (exec_date - date_achat).days if date_achat else duree

                trades.append(
                    V4Trade(
                        ticker_id=ticker_id,
                        code_bc=code_bc,
                        date_achat=str(date_achat.date()) if hasattr(date_achat, "date") else str(date_achat),
                        date_vente=str(exec_date.date()) if hasattr(exec_date, "date") else str(exec_date),
                        prix_achat=round(prix_achat, 4),
                        prix_vente=round(prix_vente, 4),
                        quantite=quantite,
                        fair_value=round(fv_at_entry, 2),
                        pv_nette=round(pv_nette, 2),
                        impot_pv=round(impot, 2),
                        duree_jours=duree_exec,
                        signal_sortie=signal_sortie,
                    )
                )
                en_position = False
                last_vente_idx = exec_idx
                continue

        if not en_position and (i - last_vente_idx) >= params["cooldown_jours"]:
            fv = get_jv_at_date(date_str)
            if fv is None or fv <= 0:
                continue

            decote = (fv - close) / close * 100
            if decote < params["decote_min_pct"]:
                continue

            timing_ok = False
            if (
                rsi is not None
                and not pd.isna(rsi)
                and rsi <= params["rsi_entry_max"]
            ):
                timing_ok = True
            if (
                bb_pct is not None
                and not pd.isna(bb_pct)
                and bb_pct <= params["bb_entry_max"]
            ):
                timing_ok = True

            if not timing_ok:
                continue

            montant = capital * params["position_size_pct"]
            _, exec_date, exec_price = _next_exec(i)
            q = max(1, int(montant / (exec_price * (1 + SLIPPAGE))))
            cout = q * exec_price * (1 + SLIPPAGE)
            fees = calculate_fees(cout)
            total_cost = cout + fees["total_fees"]

            if total_cost <= capital:
                en_position = True
                quantite = q
                prix_achat = exec_price * (1 + SLIPPAGE) + fees["total_fees"] / q
                date_achat = exec_date
                fv_at_entry = fv
                stop_price = exec_price * (1 - params["stop_loss_pct"])
                decote_at_entry = decote
                capital -= total_cost

    # Force close open position
    if en_position and len(df) > 0:
        last_date = df.index[-1]
        close = close_values[-1]
        if not pd.isna(close) and close > 0:
            duree = (last_date - date_achat).days if date_achat else 0
            prix_vente = close * (1 - SLIPPAGE)
            brut_vente = quantite * prix_vente
            fees = calculate_fees(brut_vente)
            pv_brute = (prix_vente - prix_achat) * quantite
            impot = pv_brute * 0.15 if pv_brute > 0 else 0.0
            pv_nette = pv_brute - impot - fees["total_fees"]

            trades.append(
                V4Trade(
                    ticker_id=ticker_id,
                    code_bc=code_bc,
                    date_achat=str(date_achat.date()) if hasattr(date_achat, "date") else str(date_achat),
                    date_vente=str(last_date.date()) if hasattr(last_date, "date") else str(last_date),
                    prix_achat=round(prix_achat, 4),
                    prix_vente=round(prix_vente, 4),
                    quantite=quantite,
                    fair_value=round(fv_at_entry, 2),
                    pv_nette=round(pv_nette, 2),
                    impot_pv=round(impot, 2),
                    duree_jours=duree,
                    signal_sortie="CLOTURE_FIN",
                )
            )

    nb = len(trades)
    if nb == 0:
        return V4BacktestResult(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, [], [])

    pvs = [t.pv_nette for t in trades]
    gagnants = [p for p in pvs if p > 0]
    perdants = [p for p in pvs if p <= 0]
    gross_gain = sum(gagnants) if gagnants else 0
    gross_loss = abs(sum(perdants)) if perdants else 0

    curve = [{"date": trades[0].date_achat, "equity": params["capital_initial"]}]
    cumul = params["capital_initial"]
    for t in trades:
        cumul += t.pv_nette
        curve.append({"date": t.date_vente, "equity": round(cumul, 2)})

    return V4BacktestResult(
        nb_trades=nb,
        nb_gagnants=len(gagnants),
        nb_perdants=len(perdants),
        win_rate=round(len(gagnants) / nb, 4),
        profit_factor=round(
            min(gross_gain / gross_loss, 99.99)
            if gross_loss > 0
            else (99.99 if gross_gain > 0 else 0),
            3,
        ),
        total_pv_nette=round(sum(pvs), 2),
        avg_pv_par_trade=round(sum(pvs) / nb, 2),
        avg_duree_jours=round(sum(t.duree_jours for t in trades) / nb, 1),
        max_gain=round(max(pvs), 2),
        max_perte=round(min(pvs), 2),
        trades=trades,
        equity_curve=curve,
    )
