"""CasaQuant Unified — Technical indicators engine.

Pure Python/numpy/pandas implementation. No external TA library dependency.
"""

import numpy as np
import pandas as pd


def _wilder_rma(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()


def compute_sma(series: pd.Series, length: int) -> pd.Series:
    return series.rolling(length, min_periods=length).mean()


def compute_ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False, min_periods=length).mean()


def compute_rsi(series: pd.Series, length: int = 14) -> pd.Series:
    delta = series.diff()
    gains = delta.clip(lower=0)
    losses = -delta.clip(upper=0)
    avg_gain = _wilder_rma(gains, length)
    avg_loss = _wilder_rma(losses, length)
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.mask((avg_loss == 0) & (avg_gain > 0), 100.0)
    rsi = rsi.mask((avg_gain == 0) & (avg_loss > 0), 0.0)
    rsi = rsi.mask((avg_gain == 0) & (avg_loss == 0), 50.0)
    rsi.iloc[:length] = np.nan
    return rsi


def compute_macd(
    series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> pd.DataFrame:
    ema_fast = compute_ema(series, fast)
    ema_slow = compute_ema(series, slow)
    macd = ema_fast - ema_slow
    macd_signal = macd.ewm(span=signal, adjust=False, min_periods=signal).mean()
    macd_hist = macd - macd_signal
    return pd.DataFrame(
        {
            f"MACD_{fast}_{slow}_{signal}": macd,
            f"MACDs_{fast}_{slow}_{signal}": macd_signal,
            f"MACDh_{fast}_{slow}_{signal}": macd_hist,
        },
        index=series.index,
    )


def compute_bbands(series: pd.Series, length: int = 20, std: float = 2.0) -> pd.DataFrame:
    mid = series.rolling(length, min_periods=length).mean()
    sigma = series.rolling(length, min_periods=length).std(ddof=0)
    upper = mid + std * sigma
    lower = mid - std * sigma
    pct = (series - lower) / (upper - lower).replace(0, np.nan)
    return pd.DataFrame(
        {
            f"BBL_{length}_{std:.1f}_{std:.1f}": lower,
            f"BBM_{length}_{std:.1f}_{std:.1f}": mid,
            f"BBU_{length}_{std:.1f}_{std:.1f}": upper,
            f"BBP_{length}_{std:.1f}_{std:.1f}": pct,
        },
        index=series.index,
    )


def compute_atr(df: pd.DataFrame, length: int = 14) -> pd.Series:
    prev_close = df["close"].shift(1)
    hl = df["high"] - df["low"]
    hc = (df["high"] - prev_close).abs()
    lc = (df["low"] - prev_close).abs()
    true_range = pd.Series(np.maximum(np.maximum(hl, hc), lc), index=df.index)
    atr = _wilder_rma(true_range, length)
    atr.iloc[:length] = np.nan
    return atr


def compute_adx(df: pd.DataFrame, length: int = 14) -> pd.DataFrame:
    up_move = df["high"].diff()
    down_move = -df["low"].diff()

    plus_dm = pd.Series(
        np.where((up_move > down_move) & (up_move > 0), up_move, 0.0),
        index=df.index,
    )
    minus_dm = pd.Series(
        np.where((down_move > up_move) & (down_move > 0), down_move, 0.0),
        index=df.index,
    )

    prev_close = df["close"].shift(1)
    hl = df["high"] - df["low"]
    hc = (df["high"] - prev_close).abs()
    lc = (df["low"] - prev_close).abs()
    true_range = pd.Series(np.maximum(np.maximum(hl, hc), lc), index=df.index)
    atr = _wilder_rma(true_range, length)
    plus_di = 100 * _wilder_rma(plus_dm, length) / atr.replace(0, np.nan)
    minus_di = 100 * _wilder_rma(minus_dm, length) / atr.replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0, np.nan)
    adx = _wilder_rma(dx, length)
    adx.iloc[: length * 2 - 1] = np.nan
    return pd.DataFrame(
        {
            f"DMP_{length}": plus_di,
            f"DMN_{length}": minus_di,
            f"ADX_{length}": adx,
        },
        index=df.index,
    )


def enrich_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """Enrich OHLCV DataFrame with technical indicators.

    Requires at least 30 rows. Returns original if too short.
    """
    if len(df) < 30:
        return df.copy()

    enriched = df.copy()
    close = enriched["close"]

    enriched["RSI_14"] = compute_rsi(close, 14)
    enriched = enriched.join(compute_adx(enriched, 14))
    enriched = enriched.join(compute_macd(close, 12, 26, 9))
    enriched["SMA_20"] = compute_sma(close, 20)
    enriched["SMA_50"] = compute_sma(close, 50)
    enriched["SMA_200"] = compute_sma(close, 200)
    enriched = enriched.join(compute_bbands(close, 20, 2.0))
    enriched["ATRr_14"] = compute_atr(enriched, 14)
    enriched["vol_moy_20"] = enriched["volume"].rolling(20, min_periods=20).mean()

    # Trend flags
    enriched["above_sma20"] = (close > enriched["SMA_20"]).astype(int)
    enriched["above_sma50"] = (close > enriched["SMA_50"]).astype(int)
    enriched["above_sma200"] = (close > enriched["SMA_200"]).astype(int)
    enriched["golden_cross"] = (
        (enriched["SMA_50"] > enriched["SMA_200"])
        & (enriched["SMA_50"].shift(1) <= enriched["SMA_200"].shift(1))
    ).astype(int)

    return enriched


def snapshot_last(df: pd.DataFrame) -> dict:
    """Extract latest indicator values from enriched DataFrame."""
    if df.empty:
        return {}
    last = df.iloc[-1]

    def g(key: str, fallback=None):
        v = last.get(key, fallback)
        if v is None or (isinstance(v, float) and np.isnan(v)):
            return fallback
        return round(float(v), 4)

    return {
        "prix_dernier": g("close"),
        "rsi_14": g("RSI_14"),
        "adx_14": g("ADX_14"),
        "di_plus": g("DMP_14"),
        "di_minus": g("DMN_14"),
        "macd": g("MACD_12_26_9"),
        "macd_signal": g("MACDs_12_26_9"),
        "macd_hist": g("MACDh_12_26_9"),
        "bb_upper": g("BBU_20_2.0_2.0"),
        "bb_mid": g("BBM_20_2.0_2.0"),
        "bb_lower": g("BBL_20_2.0_2.0"),
        "bb_pct": g("BBP_20_2.0_2.0"),
        "atr_14": g("ATRr_14"),
        "sma_20": g("SMA_20"),
        "sma_50": g("SMA_50"),
        "sma_200": g("SMA_200"),
        "above_sma20": int(last.get("above_sma20", 0)),
        "above_sma50": int(last.get("above_sma50", 0)),
        "above_sma200": int(last.get("above_sma200", 0)),
        "golden_cross": int(last.get("golden_cross", 0)),
        "vol_moy_20": g("vol_moy_20"),
    }
