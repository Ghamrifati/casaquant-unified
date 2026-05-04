"""Tests for 5-pillar scoring engine."""

import pytest

from app.domains.scoring.engine import (
    ScoreResult,
    backtest_quality,
    compute_final_score,
    determine_alerts,
    determine_judgment,
    determine_regime,
    pillar_liquidity,
    pillar_momentum,
    pillar_risk,
    pillar_trend,
    pillar_value,
    score_ticker,
)


class TestPillarMomentum:
    def test_rsi_optimal_zone(self):
        ind = {"rsi_14": 35, "macd_hist": 1.0, "perf_1m": 3.0, "perf_3m": 5.0}
        score = pillar_momentum(ind)
        assert score >= 80

    def test_rsi_overbought(self):
        ind = {"rsi_14": 75, "macd_hist": 1.0, "perf_1m": 3.0, "perf_3m": 5.0}
        score = pillar_momentum(ind)
        assert score <= 50

    def test_macd_negative(self):
        ind = {"rsi_14": 50, "macd_hist": -3.0, "perf_1m": -2.0, "perf_3m": -5.0}
        score = pillar_momentum(ind)
        assert score <= 40


class TestPillarTrend:
    def test_strong_uptrend(self):
        ind = {"above_sma200": 1, "above_sma50": 1, "above_sma20": 1, "adx_14": 45, "golden_cross": 1}
        score = pillar_trend(ind)
        assert score >= 80

    def test_no_trend(self):
        ind = {"above_sma200": 0, "above_sma50": 0, "above_sma20": 0, "adx_14": 10}
        score = pillar_trend(ind)
        assert score <= 20


class TestPillarRisk:
    def test_excellent_risk(self):
        ind = {"sharpe": 2.0, "max_drawdown": -5.0, "vol_annuelle": 10.0}
        bt = {"win_rate": 0.60, "profit_factor": 2.0}
        score = pillar_risk(ind, bt)
        assert score >= 80

    def test_poor_risk(self):
        ind = {"sharpe": -0.5, "max_drawdown": -60.0, "vol_annuelle": 50.0}
        score = pillar_risk(ind, None)
        assert score <= 30


class TestPillarValue:
    def test_deep_discount(self):
        ind = {"prix_dernier": 100.0, "bb_pct": 0.1}
        jv = {"fair_value_mad": 130.0}
        score = pillar_value(ind, jv)
        assert score >= 80

    def test_no_jv(self):
        ind = {"prix_dernier": 100.0, "bb_pct": 0.5}
        score = pillar_value(ind, None)
        assert score == 50  # neutral


class TestPillarLiquidity:
    def test_very_liquid(self):
        ind = {"vol_moy_20": 200_000}
        score = pillar_liquidity(ind)
        assert score == 100.0

    def test_illiquid(self):
        ind = {"vol_moy_20": 500}
        score = pillar_liquidity(ind, illiquide=True)
        assert score == 0.0


class TestFinalScore:
    def test_active_weights(self):
        score = compute_final_score(80, 70, 60, 50, 40)
        expected = round(80 * 0.30 + 70 * 0.25 + 60 * 0.20 + 50 * 0.15 + 40 * 0.10, 2)
        assert score == expected

    def test_illiquid_weights(self):
        score = compute_final_score(80, 70, 60, 50, 40, illiquide=True)
        expected = round(80 * 0.05 + 70 * 0.10 + 60 * 0.25 + 50 * 0.40 + 40 * 0.20, 2)
        assert score == expected


class TestJudgment:
    def test_fort_acheter(self):
        j, a = determine_judgment(75)
        assert j == "FORT"
        assert a == "ACHETER"

    def test_nul_vendre(self):
        j, a = determine_judgment(25)
        assert j == "NUL"
        assert a == "VENDRE"

    def test_illiquide_max_conserver(self):
        j, a = determine_judgment(70, illiquide=True)
        assert j == "MODERE"
        assert a == "CONSERVER"


class TestRegime:
    def test_haussier(self):
        r = determine_regime({"above_sma200": 1, "above_sma50": 1, "adx_14": 25})
        assert r == "HAUSSIER"

    def test_baissier(self):
        r = determine_regime({"above_sma200": 0, "above_sma50": 0, "adx_14": 25})
        assert r == "BAISSIER"


class TestAlerts:
    def test_surachete(self):
        a = determine_alerts({"rsi_14": 75, "bb_pct": 0.96})
        assert a["alerte_surachete"] is True

    def test_survendu(self):
        a = determine_alerts({"rsi_14": 20, "bb_pct": 0.04})
        assert a["alerte_survendu"] is True


class TestBacktestQuality:
    def test_robuste(self):
        assert backtest_quality({"nb_trades": 10, "win_rate": 0.40, "profit_factor": 1.5}) == 2

    def test_insuffisant(self):
        assert backtest_quality({"nb_trades": 3}) == 0


class TestScoreTicker:
    def test_full_scoring(self):
        ticker = {"id": 1, "code_bc": "ATW", "nom": "Attijariwafa", "secteur": "Bancaire", "illiquide": False}
        indicators = {
            "rsi_14": 35.0, "macd_hist": 1.5, "perf_1m": 3.0, "perf_3m": 8.0,
            "above_sma200": 1, "above_sma50": 1, "above_sma20": 1, "adx_14": 30, "golden_cross": 1,
            "sharpe": 1.2, "max_drawdown": -12.0, "vol_annuelle": 18.0,
            "prix_dernier": 150.0, "bb_pct": 0.25,
            "vol_moy_20": 50_000,
        }
        backtest = {"win_rate": 0.45, "profit_factor": 1.3, "nb_trades": 8}
        jv = {"fair_value_mad": 180.0}

        result = score_ticker(ticker, indicators, backtest, jv)
        assert isinstance(result, ScoreResult)
        assert result.ticker_id == 1
        assert result.score_final > 0
        assert result.judgment in ("FORT", "MODERE", "FAIBLE", "NUL")
        assert result.backtest_quality >= 1
