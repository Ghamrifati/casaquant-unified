"""CasaQuant Unified — 5-pillar scoring engine.

Scores each ticker on 5 pillars (momentum, trend, risk, value, liquidity)
to produce a final score out of 100.

Active (liquid) tickers:
  Momentum 30% | Trend 25% | Risk 20% | Value 15% | Liquidity 10%

Illiquid tickers:
  Value 40% | Risk 25% | Liquidity 20% | Trend 10% | Momentum 5%
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

# ── Weights ────────────────────────────────────────────────────────

WEIGHTS = {
    "momentum": Decimal("0.30"),
    "trend": Decimal("0.25"),
    "risk": Decimal("0.20"),
    "value": Decimal("0.15"),
    "liquidity": Decimal("0.10"),
}

WEIGHTS_ILLIQUID = {
    "value": Decimal("0.40"),
    "risk": Decimal("0.25"),
    "liquidity": Decimal("0.20"),
    "trend": Decimal("0.10"),
    "momentum": Decimal("0.05"),
}


def _clamp(v: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, v))


def _norm(val: float | None, low: float, high: float) -> float:
    if val is None or high == low:
        return 50.0
    return _clamp((val - low) / (high - low) * 100)


def _norm_inv(val: float | None, low: float, high: float) -> float:
    return 100.0 - _norm(val, low, high)


# ── Pillar scoring functions ──────────────────────────────────────

def pillar_momentum(indicators: dict[str, Any]) -> float:
    """Momentum pillar (0-100).

    RSI position (0-30 = oversold bonus, 70+ = penalty): 10 pts
    MACD histogram positive/negative: 10 pts
    Performance 1M, 3M: 10 pts
    """
    pts = 0.0

    rsi = indicators.get("rsi_14")
    if rsi is not None:
        if 30 <= rsi <= 45:
            pts += 10.0
        elif 45 < rsi <= 60:
            pts += 7.0
        elif 20 <= rsi < 30:
            pts += 5.0
        elif 60 < rsi <= 70:
            pts += 4.0
        elif rsi > 70:
            pts += 0.0
        else:
            pts += 3.0

    macd_h = indicators.get("macd_hist")
    if macd_h is not None:
        if macd_h > 0:
            pts += 10.0
        elif macd_h > -2:
            pts += 5.0
        else:
            pts += 0.0

    p1m = indicators.get("perf_1m")
    p3m = indicators.get("perf_3m")
    if p1m is not None and p3m is not None:
        perf_score = 0.0
        if p1m > 5:
            perf_score += 5.0
        elif p1m > 0:
            perf_score += 3.0
        elif p1m > -5:
            perf_score += 1.0
        if p3m > 10:
            perf_score += 5.0
        elif p3m > 0:
            perf_score += 3.0
        elif p3m > -10:
            perf_score += 1.0
        pts += perf_score
    elif p1m is not None:
        pts += 5.0 if p1m > 0 else 2.0
    elif p3m is not None:
        if p3m > 10:
            pts += 8.0
        elif p3m > 0:
            pts += 5.0
        elif p3m > -10:
            pts += 2.0

    return _clamp(pts / 30 * 100)


def pillar_trend(indicators: dict[str, Any]) -> float:
    """Trend pillar (0-100).

    Price vs SMA20/50/200: 12 pts
    ADX (trend strength): 8 pts
    Golden Cross: 5 pts
    """
    pts = 0.0

    above200 = indicators.get("above_sma200", 0)
    above50 = indicators.get("above_sma50", 0)
    above20 = indicators.get("above_sma20", 0)

    pts += above200 * 5.0
    pts += above50 * 4.0
    pts += above20 * 3.0

    adx = indicators.get("adx_14")
    if adx is not None:
        if adx > 40:
            pts += 8.0
        elif adx > 25:
            pts += 6.0
        elif adx > 15:
            pts += 3.0

    if indicators.get("golden_cross", 0):
        pts += 5.0

    return _clamp(pts / 25 * 100)


def pillar_risk(indicators: dict[str, Any], backtest: dict[str, Any] | None) -> float:
    """Risk/Quality pillar (0-100).

    Sharpe Ratio: 6 pts
    Max Drawdown: 6 pts
    Volatility: 4 pts
    Win Rate + Profit Factor: 4 pts
    """
    pts = 0.0

    sharpe = indicators.get("sharpe")
    if sharpe is not None:
        if sharpe > 1.5:
            pts += 6.0
        elif sharpe > 1.0:
            pts += 5.0
        elif sharpe > 0.5:
            pts += 3.5
        elif sharpe > 0:
            pts += 2.0

    mdd = indicators.get("max_drawdown")
    if mdd is not None:
        mdd_abs = abs(mdd)
        if mdd_abs < 10:
            pts += 6.0
        elif mdd_abs < 20:
            pts += 4.5
        elif mdd_abs < 35:
            pts += 2.5
        elif mdd_abs < 50:
            pts += 1.0

    vol = indicators.get("vol_annuelle")
    if vol is not None:
        if vol < 15:
            pts += 4.0
        elif vol < 25:
            pts += 3.0
        elif vol < 40:
            pts += 1.5

    if backtest:
        wr = backtest.get("win_rate", 0) or 0
        pf = backtest.get("profit_factor", 0) or 0
        if wr > 0.50 and pf > 1.5:
            pts += 4.0
        elif wr > 0.40 and pf > 1.2:
            pts += 3.0
        elif wr > 0.35:
            pts += 1.5
        else:
            pts += 0.5

    return _clamp(pts / 20 * 100)


def pillar_value(indicators: dict[str, Any], jv: dict[str, Any] | None) -> float:
    """Value pillar (0-100).

    Fair Value discount: 10 pts
    Bollinger position: 5 pts
    """
    pts = 0.0

    if jv:
        prix = indicators.get("prix_dernier")
        fv = jv.get("fair_value_mad")
        if prix and fv and prix > 0:
            discount = (fv - prix) / prix * 100
            if discount > 20:
                pts += 10.0
            elif discount > 10:
                pts += 8.0
            elif discount > 0:
                pts += 6.0
            elif discount > -10:
                pts += 4.0
            elif discount > -20:
                pts += 2.0
        else:
            pts += 5.0

    bb_pct = indicators.get("bb_pct")
    if bb_pct is not None:
        if bb_pct < 0.2:
            pts += 5.0
        elif bb_pct < 0.4:
            pts += 4.0
        elif bb_pct < 0.6:
            pts += 3.0
        elif bb_pct < 0.8:
            pts += 1.5

    return _clamp(pts / 15 * 100)


def pillar_liquidity(indicators: dict[str, Any], illiquide: bool = False) -> float:
    """Liquidity pillar (0-100)."""
    if illiquide:
        return 0.0

    vol_moy = indicators.get("vol_moy_20")
    if vol_moy is None:
        return 50.0

    if vol_moy > 100_000:
        return 100.0
    elif vol_moy > 50_000:
        return 80.0
    elif vol_moy > 20_000:
        return 60.0
    elif vol_moy > 5_000:
        return 40.0
    elif vol_moy > 1_000:
        return 20.0
    return 5.0


# ── Final score ──────────────────────────────────────────────────

def compute_final_score(
    sm: float,
    st: float,
    sr: float,
    sv: float,
    sl: float,
    illiquide: bool = False,
) -> float:
    """Compute weighted final score (0-100)."""
    if illiquide:
        return round(
            sm * float(WEIGHTS_ILLIQUID["momentum"])
            + st * float(WEIGHTS_ILLIQUID["trend"])
            + sr * float(WEIGHTS_ILLIQUID["risk"])
            + sv * float(WEIGHTS_ILLIQUID["value"])
            + sl * float(WEIGHTS_ILLIQUID["liquidity"]),
            2,
        )
    return round(
        sm * float(WEIGHTS["momentum"])
        + st * float(WEIGHTS["trend"])
        + sr * float(WEIGHTS["risk"])
        + sv * float(WEIGHTS["value"])
        + sl * float(WEIGHTS["liquidity"]),
        2,
    )


def determine_judgment(score: float, illiquide: bool = False) -> tuple[str, str]:
    """Return (judgment, advice) based on final score."""
    if illiquide:
        if score >= 65:
            return "MODERE", "CONSERVER"
        elif score >= 50:
            return "MODERE", "SURVEILLER"
        return "FAIBLE", "EVITER"

    if score >= 70:
        return "FORT", "ACHETER"
    elif score >= 60:
        return "FORT", "RENFORCER"
    elif score >= 50:
        return "MODERE", "CONSERVER"
    elif score >= 40:
        return "MODERE", "SURVEILLER"
    elif score >= 30:
        return "FAIBLE", "ALLEGER"
    return "NUL", "VENDRE"


def determine_regime(indicators: dict[str, Any]) -> str:
    """Determine market regime for a ticker."""
    above200 = indicators.get("above_sma200", 0)
    above50 = indicators.get("above_sma50", 0)
    adx = indicators.get("adx_14", 0) or 0

    if above200 and above50 and adx > 20:
        return "HAUSSIER"
    elif not above200 and not above50 and adx > 20:
        return "BAISSIER"
    return "NEUTRE"


def determine_alerts(indicators: dict[str, Any], illiquide: bool = False) -> dict[str, bool]:
    """Determine alert flags for a ticker."""
    rsi = indicators.get("rsi_14", 50) or 50
    bb_pct = indicators.get("bb_pct")
    return {
        "alerte_illiquide": illiquide,
        "alerte_surachete": rsi > 70 or (bb_pct is not None and bb_pct > 0.95),
        "alerte_survendu": rsi < 25 or (bb_pct is not None and bb_pct < 0.05),
        "alerte_breakout": bool(indicators.get("golden_cross")),
    }


def backtest_quality(backtest: dict[str, Any] | None) -> int:
    """Determine backtest quality: 0=INSUFFISANT, 1=PRUDENT, 2=ROBUSTE."""
    if backtest is None:
        return 0
    nb = backtest.get("nb_trades", 0) or 0
    wr = backtest.get("win_rate", 0) or 0
    pf = backtest.get("profit_factor", 0) or 0
    if nb < 5:
        return 0
    if wr >= 0.35 and pf >= 1.2:
        return 2
    return 1


# ── Score result DTO ─────────────────────────────────────────────

@dataclass
class ScoreResult:
    ticker_id: int
    code_bc: str
    nom: str
    secteur: str | None
    illiquide: bool

    score_momentum: float
    score_trend: float
    score_risk: float
    score_value: float
    score_liquidity: float
    score_final: float

    judgment: str
    advice: str
    regime: str

    rsi_14: float | None
    adx_14: float | None
    macd_hist: float | None
    bb_pct: float | None
    above_sma50: int
    above_sma200: int
    golden_cross: int
    vol_annuelle: float | None
    sharpe: float | None
    max_drawdown: float | None
    perf_1m: float | None
    perf_1y: float | None
    win_rate: float | None
    nb_trades: int | None
    backtest_quality: int

    alerts: dict[str, bool]


def score_ticker(
    ticker: dict[str, Any],
    indicators: dict[str, Any],
    backtest: dict[str, Any] | None,
    jv: dict[str, Any] | None,
) -> ScoreResult:
    """Compute full score for a single ticker."""
    illiquide = bool(ticker.get("illiquide"))

    sm = pillar_momentum(indicators)
    st = pillar_trend(indicators)
    sr = pillar_risk(indicators, backtest)
    sv = pillar_value(indicators, jv)
    sl = pillar_liquidity(indicators, illiquide)

    score_final = compute_final_score(sm, st, sr, sv, sl, illiquide)
    judgment, advice = determine_judgment(score_final, illiquide)
    regime = determine_regime(indicators)
    alerts = determine_alerts(indicators, illiquide)
    btq = backtest_quality(backtest)

    return ScoreResult(
        ticker_id=ticker["id"],
        code_bc=ticker["code_bc"],
        nom=ticker["nom"],
        secteur=ticker.get("secteur"),
        illiquide=illiquide,
        score_momentum=round(sm, 2),
        score_trend=round(st, 2),
        score_risk=round(sr, 2),
        score_value=round(sv, 2),
        score_liquidity=round(sl, 2),
        score_final=score_final,
        judgment=judgment,
        advice=advice,
        regime=regime,
        rsi_14=indicators.get("rsi_14"),
        adx_14=indicators.get("adx_14"),
        macd_hist=indicators.get("macd_hist"),
        bb_pct=indicators.get("bb_pct"),
        above_sma50=indicators.get("above_sma50", 0),
        above_sma200=indicators.get("above_sma200", 0),
        golden_cross=indicators.get("golden_cross", 0),
        vol_annuelle=indicators.get("vol_annuelle"),
        sharpe=indicators.get("sharpe"),
        max_drawdown=indicators.get("max_drawdown"),
        perf_1m=indicators.get("perf_1m"),
        perf_1y=indicators.get("perf_1y"),
        win_rate=backtest.get("win_rate") if backtest else None,
        nb_trades=backtest.get("nb_trades") if backtest else None,
        backtest_quality=btq,
        alerts=alerts,
    )
