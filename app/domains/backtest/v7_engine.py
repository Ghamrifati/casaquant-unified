"""CasaQuant Unified — V7 Mean-Reversion backtest engine.

Mean-reversion + MASI regime filter.
Uses SMA20 as target, with regime filter to avoid trading against the trend.
"""

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from app.domains.common.fees import calculate_fees

logger = logging.getLogger("casaquant.backtest.v7")

SLIPPAGE = 0.001


@dataclass
class V7BacktestResult:
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
    trades: list[dict]
    equity_curve: list[dict]


def backtest_ticker(
    ticker_id: int,
    code_bc: str,
    df: pd.DataFrame,
    params: dict[str, Any] | None = None,
) -> V7BacktestResult:
    """Run V7 mean-reversion backtest on a single ticker.

    TODO: full implementation from legacy strategy_v7.py
    This is a stub that preserves the interface.
    """
    logger.info("V7 backtest stub for %s", code_bc)
    return V7BacktestResult(
        nb_trades=0,
        nb_gagnants=0,
        nb_perdants=0,
        win_rate=0.0,
        profit_factor=0.0,
        total_pv_nette=0.0,
        avg_pv_par_trade=0.0,
        avg_duree_jours=0.0,
        max_gain=0.0,
        max_perte=0.0,
        trades=[],
        equity_curve=[],
    )
