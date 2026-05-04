"""CasaQuant Unified — V7 Mean-Reversion backtest engine.

Mean-reversion + MASI regime filter.
Anti-look-ahead execution: signal at t, entry at open[t+1].

Entry: 6 filters (RSI oversold, BB lower, SMA50 discount, volume, anti-falling-knife, MASI regime)
Exit: SMA20 target / RSI recovered / BB middle / stop-loss -8% / max duration 60 days
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd

from app.domains.scoring.indicators import compute_sma, compute_rsi, compute_bbands
from decimal import Decimal as _Decimal

from app.domains.portfolio.finance import calculer_frais_decimal

logger = logging.getLogger("casaquant.backtest.v7")

SLIPPAGE = 0.001

# ── Default V7 parameters ───────────────────────────────────────

DEFAULT_V7_PARAMS = {
    "version": "7.0",
    "name": "V7 Mean-Reversion + Filtre Regime MASI",
    "entree": {
        "regime_masi_required": True,
        "masi_sma_period": 200,
        "rsi_max": 30,
        "bb_lower_required": True,
        "ecart_sma50_max": -0.08,
        "volume_20j_min": 1000,
        "anti_falling_knife_60j": 0.80,
    },
    "sortie": {
        "target_sma20": True,
        "rsi_recovered": 55,
        "bb_middle": True,
        "stop_loss_pct": 0.08,
        "duree_max_jours": 60,
    },
    "execution": {
        "capital_initial": 10000,
        "position_size_pct": 0.15,
    },
    "walkforward": {
        "train_years": 4,
        "test_years": 1,
        "step_months": 6,
    },
}


# ── Enums ─────────────────────────────────────────────────────────

class SignalV7(Enum):
    ACHETER = "ACHETER"
    ATTENDRE = "ATTENDRE"


class SortieV7(Enum):
    TARGET_REVERSION = "TARGET_REVERSION"
    RSI_RECOVERED = "RSI_RECOVERED"
    BB_MIDDLE = "BB_MIDDLE"
    STOP_LOSS = "STOP_LOSS"
    DUREE_MAX = "DUREE_MAX"
    CLOTURE_FIN = "CLOTURE_FIN"


# ── Dataclasses ─────────────────────────────────────────────────

@dataclass
class V7Signal:
    ticker: str
    date: str
    signal: SignalV7
    filtres_ok: dict[str, bool] = field(default_factory=dict)


@dataclass
class V7Trade:
    ticker_id: int
    code_bc: str
    date_achat: str
    date_vente: str
    prix_achat: float
    prix_vente: float
    quantite: int
    pv_nette: float
    impot_pv: float
    duree_jours: int
    motif_sortie: SortieV7


@dataclass
class V7BacktestResult:
    nb_trades: int = 0
    nb_gagnants: int = 0
    nb_perdants: int = 0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    total_pv_nette: float = 0.0
    avg_pv_par_trade: float = 0.0
    avg_duree_jours: float = 0.0
    max_gain: float = 0.0
    max_perte: float = 0.0
    trades: list[dict] = field(default_factory=list)
    equity_curve: list[dict] = field(default_factory=list)


# ── MASI Regime ─────────────────────────────────────────────────

def compute_masi_regime(masi_df: pd.DataFrame, sma_period: int = 200) -> pd.Series:
    """Return boolean Series: True when MASI close > SMA(sma_period)."""
    if masi_df.empty or "close" not in masi_df.columns:
        return pd.Series(dtype=bool)
    sma = masi_df["close"].rolling(sma_period, min_periods=sma_period).mean()
    regime = masi_df["close"] > sma
    regime.iloc[: sma_period - 1] = False
    return regime


def get_masi_regime_at_date(
    regime_series: pd.Series, target_date: pd.Timestamp | str, no_masi_data_fallback: bool = True
) -> bool:
    """Lookup regime at date using ffill."""
    if regime_series.empty:
        return no_masi_data_fallback
    if isinstance(target_date, str):
        target_date = pd.Timestamp(target_date)
    # Get last known value <= target_date
    valid = regime_series.loc[:target_date]
    if valid.empty:
        return no_masi_data_fallback
    return bool(valid.iloc[-1])


# ── Indicators ──────────────────────────────────────────────────

def compute_meanrev_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Compute V7 indicators on OHLCV DataFrame."""
    if len(df) < 60:
        return df.copy()
    out = df.copy()
    close = out["close"]
    out["sma20"] = compute_sma(close, 20)
    out["sma50"] = compute_sma(close, 50)
    out["sma200"] = compute_sma(close, 200)
    out["rsi_14"] = compute_rsi(close, 14)
    bb = compute_bbands(close, 20, 2.0)
    out = out.join(bb)
    out["vol_moy_20"] = out["volume"].rolling(20, min_periods=20).mean()
    out["ratio_60j"] = close / close.shift(60)
    return out


# ── Entry Filters ────────────────────────────────────────────────

def evaluate_v7_signal(
    ticker_data: pd.Series | dict[str, Any],
    regime_masi_ok: bool,
    params: dict[str, Any] | None = None,
) -> V7Signal:
    """Evaluate V7 entry signal (6 filters).

    Returns V7Signal with filtres_ok dict.
    """
    p = params or DEFAULT_V7_PARAMS
    entree = p.get("entree", {})

    filtres: dict[str, bool] = {}

    # Filter 0: MASI regime (absolute priority)
    regime_required = entree.get("regime_masi_required", True)
    if regime_required and not regime_masi_ok:
        return V7Signal(
            ticker=str(ticker_data.get("code_bc", "")),
            date=str(ticker_data.get("date", "")),
            signal=SignalV7.ATTENDRE,
            filtres_ok={**{k: False for k in [
                "regime_masi", "rsi_survente", "bb_lower", "ecart_sma50", "volume", "anti_falling_knife"
            ]}, "regime_masi": False},
        )

    filtres["regime_masi"] = regime_masi_ok if regime_required else True

    # Helper to safely get float values
    def _f(key: str) -> float | None:
        v = ticker_data.get(key) if isinstance(ticker_data, dict) else getattr(ticker_data, key, None)
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return None
        return float(v)

    close = _f("close")
    rsi = _f("rsi_14")
    bb_lower = _f("BBL_20_2.0_2.0")
    bb_middle = _f("BBM_20_2.0_2.0")
    sma50 = _f("sma50")
    vol_moy = _f("vol_moy_20")
    ratio_60j = _f("ratio_60j")

    # Filter 1: RSI oversold
    filtres["rsi_survente"] = rsi is not None and rsi <= entree.get("rsi_max", 30)

    # Filter 2: BB lower
    if entree.get("bb_lower_required", True):
        filtres["bb_lower"] = close is not None and bb_lower is not None and close <= bb_lower
    else:
        filtres["bb_lower"] = True

    # Filter 3: SMA50 discount
    if sma50 is not None and sma50 > 0 and close is not None:
        ecart = (close - sma50) / sma50
        filtres["ecart_sma50"] = ecart <= entree.get("ecart_sma50_max", -0.08)
    else:
        filtres["ecart_sma50"] = False

    # Filter 4: Volume
    filtres["volume"] = vol_moy is not None and vol_moy >= entree.get("volume_20j_min", 1000)

    # Filter 5: Anti-falling-knife
    if ratio_60j is not None:
        filtres["anti_falling_knife"] = ratio_60j >= entree.get("anti_falling_knife_60j", 0.80)
    else:
        filtres["anti_falling_knife"] = False

    all_ok = all(filtres.values())
    signal = SignalV7.ACHETER if all_ok else SignalV7.ATTENDRE

    return V7Signal(
        ticker=str(ticker_data.get("code_bc", "") if isinstance(ticker_data, dict) else getattr(ticker_data, "code_bc", "")),
        date=str(ticker_data.get("date", "") if isinstance(ticker_data, dict) else getattr(ticker_data, "date", "")),
        signal=signal,
        filtres_ok=filtres,
    )


# ── Exit Logic ──────────────────────────────────────────────────

def check_v7_exit(
    position: dict[str, Any],
    current_data: pd.Series | dict[str, Any],
    params: dict[str, Any] | None = None,
) -> SortieV7 | None:
    """Check if position should be exited.

    Priority order:
    1. TARGET_REVERSION (close >= sma20)
    2. RSI_RECOVERED (rsi >= threshold)
    3. BB_MIDDLE (close >= bb middle)
    4. STOP_LOSS (close < prix_achat * (1 - stop_loss_pct))
    5. DUREE_MAX (duree >= duree_max_jours)
    """
    p = params or DEFAULT_V7_PARAMS
    sortie = p.get("sortie", {})

    def _f(key: str) -> float | None:
        v = current_data.get(key) if isinstance(current_data, dict) else getattr(current_data, key, None)
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return None
        return float(v)

    prix_achat = position.get("prix_achat", 0)
    duree = position.get("duree_jours", 0)
    close = _f("close")
    rsi = _f("rsi_14")
    sma20 = _f("sma20")
    bb_middle = _f("BBM_20_2.0_2.0")

    # 1. Target SMA20
    if sortie.get("target_sma20", True) and sma20 is not None and close is not None and close >= sma20:
        return SortieV7.TARGET_REVERSION

    # 2. RSI recovered
    rsi_threshold = sortie.get("rsi_recovered", 55)
    if rsi is not None and rsi >= rsi_threshold:
        return SortieV7.RSI_RECOVERED

    # 3. BB middle (fallback if sma20 missing)
    if sortie.get("bb_middle", True) and bb_middle is not None and close is not None and close >= bb_middle:
        return SortieV7.BB_MIDDLE

    # 4. Stop-loss
    sl_pct = sortie.get("stop_loss_pct", 0.08)
    if prix_achat > 0 and close is not None and close < prix_achat * (1 - sl_pct):
        return SortieV7.STOP_LOSS

    # 5. Max duration
    max_days = sortie.get("duree_max_jours", 60)
    if duree >= max_days:
        return SortieV7.DUREE_MAX

    return None


# ── Single-Ticker Backtest ──────────────────────────────────────

def backtest_v7_ticker(
    ticker_id: int,
    code_bc: str,
    df: pd.DataFrame,
    masi_regime: pd.Series | None = None,
    params: dict[str, Any] | None = None,
    no_masi_data_fallback: bool = True,
) -> V7BacktestResult:
    """Run V7 mean-reversion backtest on a single ticker."""
    p = params or DEFAULT_V7_PARAMS
    exec_params = p.get("execution", {})
    capital = float(exec_params.get("capital_initial", 10000))
    pos_size_pct = float(exec_params.get("position_size_pct", 0.15))

    if len(df) < 100:
        logger.warning("V7: insufficient data for %s (%d rows < 100)", code_bc, len(df))
        return V7BacktestResult()

    df_ind = compute_meanrev_indicators(df)
    if df_ind.empty or df_ind["close"].isna().all():
        return V7BacktestResult()

    trades: list[V7Trade] = []
    equity_curve: list[dict] = []
    position: dict[str, Any] | None = None

    for i in range(len(df_ind) - 1):
        row_t = df_ind.iloc[i]
        row_next = df_ind.iloc[i + 1]
        current_date = df_ind.index[i] if hasattr(df_ind.index[i], "strftime") else str(df_ind.index[i])

        # Update position duration
        if position is not None:
            position["duree_jours"] += 1

        # Exit check
        if position is not None:
            exit_motif = check_v7_exit(position, row_t, p)
            if exit_motif:
                exec_price = row_next["open"] if not pd.isna(row_next["open"]) else (
                    row_next["close"] if not pd.isna(row_next["close"]) else row_t["close"]
                )
                exec_price = float(exec_price) * (1 - SLIPPAGE)

                qty = position["quantite"]
                pv_brute = (exec_price - position["prix_achat"]) * qty
                impot = pv_brute * 0.15 if pv_brute > 0 else 0.0
                frais = float(calculer_frais_decimal(
                    _Decimal(str(abs(pv_brute)))
                ).total_frais)
                pv_nette = pv_brute - impot - frais

                capital += pv_nette

                trades.append(V7Trade(
                    ticker_id=ticker_id,
                    code_bc=code_bc,
                    date_achat=position["date_achat"],
                    date_vente=str(current_date),
                    prix_achat=position["prix_achat"],
                    prix_vente=exec_price,
                    quantite=qty,
                    pv_nette=pv_nette,
                    impot_pv=impot,
                    duree_jours=position["duree_jours"],
                    motif_sortie=exit_motif,
                ))
                equity_curve.append({"date": str(current_date), "capital": round(capital, 2)})
                position = None
                continue

        # Entry check
        if position is None:
            regime_ok = True
            if masi_regime is not None and p.get("entree", {}).get("regime_masi_required", True):
                regime_ok = get_masi_regime_at_date(
                    masi_regime, current_date, no_masi_data_fallback=no_masi_data_fallback
                )

            sig = evaluate_v7_signal(row_t, regime_ok, p)
            if sig.signal == SignalV7.ACHETER:
                exec_price = row_next["open"] if not pd.isna(row_next["open"]) else (
                    row_next["close"] if not pd.isna(row_next["close"]) else row_t["close"]
                )
                exec_price = float(exec_price) * (1 + SLIPPAGE)
                montant = capital * pos_size_pct
                qty = max(1, int(montant / exec_price))

                position = {
                    "prix_achat": exec_price,
                    "quantite": qty,
                    "date_achat": str(current_date),
                    "duree_jours": 0,
                }
                equity_curve.append({"date": str(current_date), "capital": round(capital, 2)})

    # Force close at end of data
    if position is not None:
        last_row = df_ind.iloc[-1]
        exec_price = float(last_row["close"]) * (1 - SLIPPAGE)
        qty = position["quantite"]
        pv_brute = (exec_price - position["prix_achat"]) * qty
        impot = pv_brute * 0.15 if pv_brute > 0 else 0.0
        frais = float(_calculer_frais_decimal(
            __import__("decimal").Decimal(str(abs(pv_brute)))
        ).total_frais)
        pv_nette = pv_brute - impot - frais
        capital += pv_nette

        trades.append(V7Trade(
            ticker_id=ticker_id,
            code_bc=code_bc,
            date_achat=position["date_achat"],
            date_vente=str(df_ind.index[-1]) if hasattr(df_ind.index[-1], "strftime") else str(df_ind.index[-1]),
            prix_achat=position["prix_achat"],
            prix_vente=exec_price,
            quantite=qty,
            pv_nette=pv_nette,
            impot_pv=impot,
            duree_jours=position["duree_jours"],
            motif_sortie=SortieV7.CLOTURE_FIN,
        ))
        equity_curve.append({"date": str(df_ind.index[-1]), "capital": round(capital, 2)})

    # Build result
    if not trades:
        return V7BacktestResult()

    gains = [t.pv_nette for t in trades if t.pv_nette > 0]
    pertes = [t.pv_nette for t in trades if t.pv_nette < 0]
    gross_gain = sum(gains) if gains else 0.0
    gross_loss = abs(sum(pertes)) if pertes else 0.0
    pf = gross_gain / gross_loss if gross_loss > 0 else (99.99 if gross_gain > 0 else 0.0)

    return V7BacktestResult(
        nb_trades=len(trades),
        nb_gagnants=len(gains),
        nb_perdants=len(pertes),
        win_rate=round(len(gains) / len(trades) * 100, 2),
        profit_factor=round(pf, 2),
        total_pv_nette=round(sum(t.pv_nette for t in trades), 2),
        avg_pv_par_trade=round(sum(t.pv_nette for t in trades) / len(trades), 2),
        avg_duree_jours=round(sum(t.duree_jours for t in trades) / len(trades), 2),
        max_gain=round(max(t.pv_nette for t in trades), 2),
        max_perte=round(min(t.pv_nette for t in trades), 2),
        trades=[
            {
                "date_achat": t.date_achat,
                "date_vente": t.date_vente,
                "prix_achat": t.prix_achat,
                "prix_vente": t.prix_vente,
                "quantite": t.quantite,
                "pv_nette": t.pv_nette,
                "duree_jours": t.duree_jours,
                "motif_sortie": t.motif_sortie.value,
            }
            for t in trades
        ],
        equity_curve=equity_curve,
    )


# ── Walk-Forward ────────────────────────────────────────────────

@dataclass
class V7WFWindow:
    train_start: str
    train_end: str
    test_start: str
    test_end: str
    is_result: V7BacktestResult = field(default_factory=V7BacktestResult)
    oos_result: V7BacktestResult = field(default_factory=V7BacktestResult)

    @property
    def ratio_wr(self) -> float | None:
        if self.is_result.win_rate and self.is_result.win_rate > 0:
            return round(self.oos_result.win_rate / self.is_result.win_rate, 2)
        return None

    @property
    def ratio_pf(self) -> float | None:
        if self.is_result.profit_factor and self.is_result.profit_factor > 0:
            return round(self.oos_result.profit_factor / self.is_result.profit_factor, 2)
        return None


@dataclass
class V7WFReport:
    computed_at: str
    nb_windows: int
    windows: list[V7WFWindow]
    verdict: str = "FRAGILE"
    avg_ratio_wr: float | None = None
    avg_ratio_pf: float | None = None
    total_oos_pv: float = 0.0
    avg_oos_wr: float = 0.0
    avg_oos_pf: float = 0.0


def run_walkforward_v7(
    ticker_id: int,
    code_bc: str,
    df: pd.DataFrame,
    masi_regime: pd.Series | None = None,
    params: dict[str, Any] | None = None,
) -> V7WFReport:
    """Run 4Y IS / 1Y OOS walk-forward on a single ticker.

    Steps: 6 months. Returns V7WFReport with verdict.
    """
    p = params or DEFAULT_V7_PARAMS
    wf = p.get("walkforward", {})
    train_y = wf.get("train_years", 4)
    test_y = wf.get("test_years", 1)
    step_m = wf.get("step_months", 6)

    if len(df) < 252 * (train_y + test_y):
        return V7WFReport(
            computed_at=str(pd.Timestamp.now()),
            nb_windows=0,
            windows=[],
            verdict="INSUFFISANT",
        )

    windows: list[V7WFWindow] = []
    start = df.index[0]
    end = df.index[-1]

    current = start
    while True:
        train_start = current
        train_end = current + pd.DateOffset(years=train_y) - pd.Timedelta(days=1)
        test_start = train_end + pd.Timedelta(days=1)
        test_end = test_start + pd.DateOffset(years=test_y) - pd.Timedelta(days=1)

        if test_end > end:
            break

        train_df = df.loc[train_start:train_end]
        test_df = df.loc[test_start:test_end]

        is_res = backtest_v7_ticker(ticker_id, code_bc, train_df, masi_regime, p)
        oos_res = backtest_v7_ticker(ticker_id, code_bc, test_df, masi_regime, p)

        windows.append(V7WFWindow(
            train_start=str(train_start.date()),
            train_end=str(train_end.date()),
            test_start=str(test_start.date()),
            test_end=str(test_end.date()),
            is_result=is_res,
            oos_result=oos_res,
        ))

        current = current + pd.DateOffset(months=step_m)
        if current + pd.DateOffset(years=train_y + test_y) > end:
            break

    if not windows:
        return V7WFReport(
            computed_at=str(pd.Timestamp.now()),
            nb_windows=0,
            windows=[],
            verdict="INSUFFISANT",
        )

    wrs = [w.oos_result.win_rate for w in windows if w.oos_result.nb_trades > 0]
    pfs = [w.oos_result.profit_factor for w in windows if w.oos_result.nb_trades > 0]
    total_pv = sum(w.oos_result.total_pv_nette for w in windows)
    avg_wr = round(sum(wrs) / len(wrs), 2) if wrs else 0.0
    avg_pf = round(sum(pfs) / len(pfs), 2) if pfs else 0.0

    verdict = "FRAGILE"
    if avg_wr >= 55 and total_pv > 0:
        verdict = "ROBUSTE"
    elif avg_wr >= 45 and total_pv > 0:
        verdict = "PROMETTEUSE"

    return V7WFReport(
        computed_at=str(pd.Timestamp.now()),
        nb_windows=len(windows),
        windows=windows,
        verdict=verdict,
        avg_oos_wr=avg_wr,
        avg_oos_pf=avg_pf,
        total_oos_pv=round(total_pv, 2),
    )
