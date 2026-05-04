"""Tests for portfolio finance engine (CMP CDVM, fees, P&L)."""

import pytest

from app.domains.portfolio.finance import (
    calculer_achat,
    calculer_vente,
    recalculer_cmp,
    calculer_pnl_latent,
    FraisBVC,
)


class TestCalculerAchat:
    def test_basic(self):
        r = calculer_achat(100, 50.0)
        assert r.prix_brut == 5000.0
        assert r.montant_net > r.prix_brut  # fees added
        assert r.frais.total_frais > 0
        assert r.plus_value_brute == 0.0
        assert r.montant_encaisse == 0.0

    def test_min_brokerage(self):
        # Small amount should trigger min brokerage (10 MAD)
        r = calculer_achat(1, 5.0)
        assert r.frais.commission_courtage == 10.0  # min fee
        assert r.frais.total_frais > 10.0  # + tax + vat


class TestCalculerVente:
    def test_profit(self):
        # Buy at 50, sell at 60 → profit
        r = calculer_vente(100, 60.0, cmp=50.0)
        assert r.plus_value_brute == 1000.0
        assert r.impot_pv == 150.0  # 15% of 1000
        assert r.profit_net == 850.0
        assert r.montant_encaisse == pytest.approx(6000 - r.frais.total_frais - 150, 0.01)

    def test_loss(self):
        # Buy at 50, sell at 40 → loss, no capital gains tax
        r = calculer_vente(100, 40.0, cmp=50.0)
        assert r.plus_value_brute == -1000.0
        assert r.impot_pv == 0.0
        assert r.profit_net == -1000.0

    def test_zero_gain(self):
        r = calculer_vente(100, 50.0, cmp=50.0)
        assert r.plus_value_brute == 0.0
        assert r.impot_pv == 0.0


class TestRecalculerCmp:
    def test_single_buy(self):
        txs = [{"ticker_id": 1, "type": "ACHAT", "quantite": 100, "montant_net": 5100.0}]
        pos = recalculer_cmp(txs)
        assert pos[1]["cmp"] == pytest.approx(51.0, 0.01)
        assert pos[1]["quantite"] == 100

    def test_two_buys_average(self):
        txs = [
            {"ticker_id": 1, "type": "ACHAT", "quantite": 100, "montant_net": 5000.0},
            {"ticker_id": 1, "type": "ACHAT", "quantite": 100, "montant_net": 6000.0},
        ]
        pos = recalculer_cmp(txs)
        assert pos[1]["cmp"] == pytest.approx(55.0, 0.01)  # (5000+6000)/200
        assert pos[1]["quantite"] == 200

    def test_sale_preserves_cmp(self):
        txs = [
            {"ticker_id": 1, "type": "ACHAT", "quantite": 100, "montant_net": 5000.0},
            {"ticker_id": 1, "type": "VENTE", "quantite": 50, "montant_net": 0.0},
        ]
        pos = recalculer_cmp(txs)
        assert pos[1]["cmp"] == pytest.approx(50.0, 0.01)  # unchanged
        assert pos[1]["quantite"] == 50
        assert pos[1]["cout_total"] == pytest.approx(2500.0, 0.01)

    def test_total_sale_zero_qty(self):
        txs = [
            {"ticker_id": 1, "type": "ACHAT", "quantite": 100, "montant_net": 5000.0},
            {"ticker_id": 1, "type": "VENTE", "quantite": 100, "montant_net": 0.0},
        ]
        pos = recalculer_cmp(txs)
        assert pos[1]["quantite"] == 0
        assert pos[1]["cout_total"] == 0.0

    def test_multi_ticker(self):
        txs = [
            {"ticker_id": 1, "type": "ACHAT", "quantite": 100, "montant_net": 5000.0},
            {"ticker_id": 2, "type": "ACHAT", "quantite": 50, "montant_net": 3000.0},
        ]
        pos = recalculer_cmp(txs)
        assert pos[1]["cmp"] == pytest.approx(50.0, 0.01)
        assert pos[2]["cmp"] == pytest.approx(60.0, 0.01)


class TestPnlLatent:
    def test_positive(self):
        pnl = calculer_pnl_latent(100, 50.0, 60.0)
        assert pnl["pnl_brut"] == 1000.0
        assert pnl["pnl_pct"] == 20.0

    def test_negative(self):
        pnl = calculer_pnl_latent(100, 50.0, 40.0)
        assert pnl["pnl_brut"] == -1000.0
        assert pnl["pnl_pct"] == -20.0

    def test_zero(self):
        pnl = calculer_pnl_latent(100, 50.0, 50.0)
        assert pnl["pnl_brut"] == 0.0
        assert pnl["pnl_pct"] == 0.0


class TestFraisBvc:
    def test_rates(self):
        f = calculer_achat(1000, 100.0).frais
        # 0.6% brokerage = 600, 0.1% tax = 100, 10% vat on brokerage = 60
        assert f.commission_courtage == pytest.approx(600.0, 0.01)
        assert f.impot_bourse == pytest.approx(100.0, 0.01)
        assert f.tva == pytest.approx(60.0, 0.01)
        assert f.total_frais == pytest.approx(760.0, 0.01)
