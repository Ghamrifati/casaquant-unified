"""Tests for technical indicators engine."""

import numpy as np
import pandas as pd
import pytest

from app.domains.scoring.indicators import (
    compute_adx,
    compute_atr,
    compute_bbands,
    compute_ema,
    compute_macd,
    compute_rsi,
    compute_sma,
    enrich_ohlcv,
    snapshot_last,
)


class TestSMA:
    def test_basic(self):
        s = pd.Series([1, 2, 3, 4, 5])
        sma = compute_sma(s, 3)
        assert pd.isna(sma.iloc[0])
        assert pd.isna(sma.iloc[1])
        assert sma.iloc[2] == 2.0
        assert sma.iloc[4] == 4.0


class TestEMA:
    def test_basic(self):
        s = pd.Series([1, 2, 3, 4, 5])
        ema = compute_ema(s, 3)
        assert pd.isna(ema.iloc[0])
        assert pd.isna(ema.iloc[1])
        assert ema.iloc[2] == 2.25  # pandas ewm seed behaviour
        assert ema.iloc[-1] > ema.iloc[-2]


class TestRSI:
    def test_overbought(self):
        s = pd.Series([10] * 10 + [20] * 5)
        rsi = compute_rsi(s, 14)
        assert rsi.iloc[-1] > 70

    def test_oversold(self):
        s = pd.Series([20] * 10 + [10] * 5)
        rsi = compute_rsi(s, 14)
        assert rsi.iloc[-1] < 30

    def test_neutral(self):
        s = pd.Series([10] * 20)
        rsi = compute_rsi(s, 14)
        assert 40 < rsi.iloc[-1] < 60


class TestMACD:
    def test_columns(self):
        s = pd.Series(np.random.randn(100).cumsum() + 100)
        macd = compute_macd(s, 12, 26, 9)
        assert "MACD_12_26_9" in macd.columns
        assert "MACDs_12_26_9" in macd.columns
        assert "MACDh_12_26_9" in macd.columns


class TestBBands:
    def test_pct_range(self):
        s = pd.Series(np.random.randn(100).cumsum() + 100)
        bb = compute_bbands(s, 20, 2.0)
        pct = bb["BBP_20_2.0_2.0"]
        assert pct.min() >= -0.5
        assert pct.max() <= 1.5


class TestATR:
    def test_positive(self):
        df = pd.DataFrame({
            "high": [105, 106, 107, 108, 109],
            "low": [95, 96, 97, 98, 99],
            "close": [100, 101, 102, 103, 104],
        })
        atr = compute_atr(df, 2)
        assert atr.iloc[-1] > 0


class TestADX:
    def test_range(self):
        df = pd.DataFrame({
            "high": pd.Series([100 + 2 * i for i in range(50)]),
            "low": pd.Series([100 + i for i in range(50)]),
            "close": pd.Series([100 + 1.5 * i for i in range(50)]),
        })
        adx = compute_adx(df, 14)
        assert "ADX_14" in adx.columns
        assert adx["ADX_14"].dropna().min() >= 0
        assert adx["ADX_14"].dropna().max() <= 100


class TestEnrichOHLCV:
    def test_enrichment(self):
        np.random.seed(42)
        df = pd.DataFrame({
            "open": np.random.randn(300).cumsum() + 100,
            "high": np.random.randn(300).cumsum() + 105,
            "low": np.random.randn(300).cumsum() + 95,
            "close": np.random.randn(300).cumsum() + 100,
            "volume": np.random.randint(1000, 100000, 300),
        })
        enriched = enrich_ohlcv(df)
        assert "RSI_14" in enriched.columns
        assert "SMA_200" in enriched.columns
        assert "MACD_12_26_9" in enriched.columns
        assert "above_sma200" in enriched.columns

    def test_too_short(self):
        df = pd.DataFrame({"open": [1, 2], "high": [2, 3], "low": [0, 1], "close": [1, 2], "volume": [100, 200]})
        enriched = enrich_ohlcv(df)
        assert "RSI_14" not in enriched.columns


class TestSnapshotLast:
    def test_extraction(self):
        np.random.seed(42)
        df = pd.DataFrame({
            "open": np.random.randn(300).cumsum() + 100,
            "high": np.random.randn(300).cumsum() + 105,
            "low": np.random.randn(300).cumsum() + 95,
            "close": np.random.randn(300).cumsum() + 100,
            "volume": np.random.randint(1000, 100000, 300),
        })
        enriched = enrich_ohlcv(df)
        snap = snapshot_last(enriched)
        assert "rsi_14" in snap
        assert "sma_200" in snap
        assert "bb_pct" in snap
