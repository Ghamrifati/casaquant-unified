"""Tests for V7 mean-reversion backtest engine."""

import numpy as np
import pandas as pd
import pytest

from app.domains.backtest.v7_engine import (
    DEFAULT_V7_PARAMS,
    SignalV7,
    SortieV7,
    V7BacktestResult,
    V7Signal,
    backtest_v7_ticker,
    check_v7_exit,
    compute_masi_regime,
    compute_meanrev_indicators,
    evaluate_v7_signal,
    get_masi_regime_at_date,
    run_walkforward_v7,
)


class TestMasiRegime:
    def test_bullish(self):
        df = pd.DataFrame({
            "close": [100 + i for i in range(250)],
        })
        regime = compute_masi_regime(df, sma_period=200)
        assert bool(regime.iloc[-1]) is True
        assert bool(regime.iloc[0]) is False  # warmup

    def test_bearish(self):
        df = pd.DataFrame({
            "close": [400 - i for i in range(250)],
        })
        regime = compute_masi_regime(df, sma_period=200)
        assert bool(regime.iloc[-1]) is False

    def test_lookup(self):
        df = pd.DataFrame({
            "close": [100 + i for i in range(250)],
        })
        regime = compute_masi_regime(df, sma_period=200)
        assert get_masi_regime_at_date(regime, 249, no_masi_data_fallback=True) is True
        assert get_masi_regime_at_date(regime, 10, no_masi_data_fallback=True) is False


class TestEntryFilters:
    def test_all_pass(self):
        row = {
            "code_bc": "TEST",
            "date": "2024-01-01",
            "close": 80.0,
            "rsi_14": 25.0,
            "BBL_20_2.0_2.0": 85.0,
            "sma50": 90.0,
            "vol_moy_20": 2000.0,
            "ratio_60j": 0.85,
        }
        sig = evaluate_v7_signal(row, regime_masi_ok=True, params=DEFAULT_V7_PARAMS)
        assert sig.signal == SignalV7.ACHETER
        assert all(sig.filtres_ok.values())

    def test_rsi_fail(self):
        row = {
            "code_bc": "TEST",
            "date": "2024-01-01",
            "close": 80.0,
            "rsi_14": 45.0,
            "BBL_20_2.0_2.0": 85.0,
            "sma50": 90.0,
            "vol_moy_20": 2000.0,
            "ratio_60j": 0.85,
        }
        sig = evaluate_v7_signal(row, regime_masi_ok=True, params=DEFAULT_V7_PARAMS)
        assert sig.signal == SignalV7.ATTENDRE
        assert sig.filtres_ok["rsi_survente"] is False

    def test_regime_fail(self):
        row = {
            "code_bc": "TEST",
            "date": "2024-01-01",
            "close": 80.0,
            "rsi_14": 25.0,
            "BBL_20_2.0_2.0": 85.0,
            "sma50": 90.0,
            "vol_moy_20": 2000.0,
            "ratio_60j": 0.85,
        }
        sig = evaluate_v7_signal(row, regime_masi_ok=False, params=DEFAULT_V7_PARAMS)
        assert sig.signal == SignalV7.ATTENDRE

    def test_regime_not_required(self):
        params = DEFAULT_V7_PARAMS.copy()
        params["entree"] = {**DEFAULT_V7_PARAMS["entree"], "regime_masi_required": False}
        row = {
            "code_bc": "TEST",
            "date": "2024-01-01",
            "close": 80.0,
            "rsi_14": 25.0,
            "BBL_20_2.0_2.0": 85.0,
            "sma50": 90.0,
            "vol_moy_20": 2000.0,
            "ratio_60j": 0.85,
        }
        sig = evaluate_v7_signal(row, regime_masi_ok=False, params=params)
        assert sig.signal == SignalV7.ACHETER


class TestExitLogic:
    def test_target_sma20(self):
        pos = {"prix_achat": 80.0, "duree_jours": 5}
        row = {"close": 95.0, "sma20": 90.0, "rsi_14": 40.0, "BBM_20_2.0_2.0": 92.0}
        exit_motif = check_v7_exit(pos, row)
        assert exit_motif == SortieV7.TARGET_REVERSION

    def test_rsi_recovered(self):
        pos = {"prix_achat": 80.0, "duree_jours": 5}
        row = {"close": 85.0, "sma20": 90.0, "rsi_14": 60.0, "BBM_20_2.0_2.0": 92.0}
        exit_motif = check_v7_exit(pos, row)
        assert exit_motif == SortieV7.RSI_RECOVERED

    def test_stop_loss(self):
        pos = {"prix_achat": 100.0, "duree_jours": 5}
        row = {"close": 90.0, "sma20": 110.0, "rsi_14": 20.0, "BBM_20_2.0_2.0": 105.0}
        exit_motif = check_v7_exit(pos, row)
        assert exit_motif == SortieV7.STOP_LOSS

    def test_duree_max(self):
        pos = {"prix_achat": 100.0, "duree_jours": 65}
        row = {"close": 99.0, "sma20": 110.0, "rsi_14": 20.0, "BBM_20_2.0_2.0": 105.0}
        exit_motif = check_v7_exit(pos, row)
        assert exit_motif == SortieV7.DUREE_MAX

    def test_no_exit(self):
        pos = {"prix_achat": 100.0, "duree_jours": 5}
        row = {"close": 99.0, "sma20": 110.0, "rsi_14": 20.0, "BBM_20_2.0_2.0": 105.0}
        exit_motif = check_v7_exit(pos, row)
        assert exit_motif is None


class TestBacktestV7Ticker:
    def _build_df(self, n=300) -> pd.DataFrame:
        """Build synthetic OHLCV with a mean-reversion pattern."""
        np.random.seed(42)
        close = np.cumsum(np.random.randn(n) * 0.5) + 100
        if n > 130:
            close[100:110] = 80  # dip
            close[110:130] = np.linspace(80, 110, 20)  # recovery
        elif n > 100:
            close[100:min(110, n)] = 80
        high = close + np.abs(np.random.randn(n)) * 0.5
        low = close - np.abs(np.random.randn(n)) * 0.5
        open_price = close + np.random.randn(n) * 0.2
        volume = np.random.randint(5000, 20000, n)
        idx = pd.date_range("2020-01-01", periods=n, freq="B")
        return pd.DataFrame({
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }, index=idx)

    def test_backtest_runs(self):
        df = self._build_df(300)
        result = backtest_v7_ticker(1, "TEST", df)
        assert isinstance(result, V7BacktestResult)
        # May have 0 trades if no signals generated in synthetic data

    def test_backtest_with_masi_regime(self):
        df = self._build_df(300)
        masi = pd.Series([True] * 300, index=df.index)
        result = backtest_v7_ticker(1, "TEST", df, masi_regime=masi)
        assert isinstance(result, V7BacktestResult)

    def test_insufficient_data(self):
        df = self._build_df(50)
        result = backtest_v7_ticker(1, "TEST", df)
        assert result.nb_trades == 0


class TestWalkForwardV7:
    def _build_df(self, n=1500) -> pd.DataFrame:
        np.random.seed(42)
        close = np.cumsum(np.random.randn(n) * 0.3) + 100
        high = close + np.abs(np.random.randn(n)) * 0.5
        low = close - np.abs(np.random.randn(n)) * 0.5
        open_price = close + np.random.randn(n) * 0.2
        volume = np.random.randint(5000, 20000, n)
        idx = pd.date_range("2020-01-01", periods=n, freq="B")
        return pd.DataFrame({
            "open": open_price,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        }, index=idx)

    def test_walkforward_runs(self):
        df = self._build_df(1500)
        report = run_walkforward_v7(1, "TEST", df)
        assert report.nb_windows >= 1
        assert report.verdict in ("ROBUSTE", "PROMETTEUSE", "FRAGILE", "INSUFFISANT")

    def test_insufficient_data(self):
        df = self._build_df(200)
        report = run_walkforward_v7(1, "TEST", df)
        assert report.verdict == "INSUFFISANT"
