"""Tests for BVC fee calculation."""

import pytest

from app.domains.common.fees import calculate_fees, round_trip_fees


class TestCalculateFees:
    def test_standard_buy(self):
        result = calculate_fees(10000.0)
        assert result["gross_amount"] == 10000.0
        assert result["brokerage"] == 60.0  # 0.6%
        assert result["tax"] == 10.0  # 0.1%
        assert result["vat"] == 6.0  # 10% of brokerage
        assert result["total_fees"] == 76.0
        assert result["net_amount"] == 10076.0

    def test_min_brokerage(self):
        result = calculate_fees(100.0)
        assert result["brokerage"] == 10.0  # min 10 MAD
        assert result["tax"] == 0.1
        assert result["vat"] == 1.0

    def test_round_trip(self):
        result = round_trip_fees(10000.0)
        assert result["round_trip_fees"] == 152.0  # 2 * 76
        assert result["round_trip_pct"] == 1.52
