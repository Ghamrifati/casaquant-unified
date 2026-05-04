"""CasaQuant Unified — 6-step recalc pipeline.

Orchestrates the daily computation workflow:
1. Load OHLCV
2. Compute indicators
3. Backtest V4 + V7
4. Scoring
5. Portfolio recalc
6. Quality report
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

import pandas as pd
from sqlmodel import Session

from app.domains.backtest.v4_engine import backtest_ticker as backtest_v4
from app.domains.backtest.v7_engine import backtest_ticker as backtest_v7
from app.domains.market.models import OHLCV
from app.domains.scoring.engine import ScoreResult, score_ticker
from app.domains.scoring.indicators import enrich_ohlcv, snapshot_last

logger = logging.getLogger("casaquant.pipeline.recalc")


@dataclass
class StepLog:
    numero: int
    nom: str
    status: str  # OK | ERREUR | WARNING
    duree_s: float
    detail: dict = field(default_factory=dict)
    message: str = ""


@dataclass
class RecalcReport:
    status: str  # OK | ECHEC | PARTIEL
    duree_s: float
    etapes: list[StepLog]
    message: str = ""

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "duree_s": self.duree_s,
            "message": self.message,
            "etapes": [
                {
                    "etape": e.numero,
                    "nom": e.nom,
                    "status": e.status,
                    "duree_s": e.duree_s,
                    "detail": e.detail,
                    "message": e.message,
                }
                for e in self.etapes
            ],
        }


class RecalcPipeline:
    """6-step recalc pipeline."""

    def __init__(self, session: Session):
        self.session = session
        self.report = RecalcReport(status="OK", duree_s=0.0, etapes=[], message="")

    def run(self, progress_callback: Callable | None = None) -> RecalcReport:
        """Run all 6 steps."""
        import time

        t0 = time.perf_counter()
        logger.info("Recalc pipeline started")

        try:
            self._step1_load_ohlcv()
            if progress_callback:
                progress_callback(1, 6)

            self._step2_compute_indicators()
            if progress_callback:
                progress_callback(2, 6)

            self._step3_backtest()
            if progress_callback:
                progress_callback(3, 6)

            self._step4_scoring()
            if progress_callback:
                progress_callback(4, 6)

            self._step5_portfolio()
            if progress_callback:
                progress_callback(5, 6)

            self._step6_quality()
            if progress_callback:
                progress_callback(6, 6)

        except Exception as exc:
            logger.exception("Recalc pipeline failed: %s", exc)
            self.report.status = "ECHEC"
            self.report.message = str(exc)

        self.report.duree_s = round(time.perf_counter() - t0, 2)
        logger.info("Recalc pipeline finished in %.2fs — status=%s", self.report.duree_s, self.report.status)
        return self.report

    def _log_step(self, numero: int, nom: str, status: str, duree: float, detail: dict, msg: str = ""):
        self.report.etapes.append(StepLog(numero, nom, status, duree, detail, msg))

    def _step1_load_ohlcv(self):
        """Step 1: Load OHLCV data."""
        import time

        t0 = time.perf_counter()
        logger.info("Step 1: Loading OHLCV")
        # TODO: implement bulk OHLCV loading
        self._log_step(1, "Chargement OHLCV", "OK", time.perf_counter() - t0, {"tickers_loaded": 0})

    def _step2_compute_indicators(self):
        """Step 2: Compute technical indicators."""
        import time

        t0 = time.perf_counter()
        logger.info("Step 2: Computing indicators")
        # TODO: implement indicator computation
        self._log_step(2, "Calcul indicateurs", "OK", time.perf_counter() - t0, {"tickers_processed": 0})

    def _step3_backtest(self):
        """Step 3: Run backtest V4 + V7."""
        import time

        t0 = time.perf_counter()
        logger.info("Step 3: Backtest V4 + V7")
        # TODO: implement backtest execution
        self._log_step(3, "Backtest V4/V7", "OK", time.perf_counter() - t0, {"v4_trades": 0, "v7_trades": 0})

    def _step4_scoring(self):
        """Step 4: Compute 5-pillar scoring."""
        import time

        t0 = time.perf_counter()
        logger.info("Step 4: Computing scoring")
        # TODO: implement scoring
        self._log_step(4, "Scoring", "OK", time.perf_counter() - t0, {"tickers_scored": 0})

    def _step5_portfolio(self):
        """Step 5: Recalculate portfolio P&L."""
        import time

        t0 = time.perf_counter()
        logger.info("Step 5: Portfolio recalc")
        # TODO: implement portfolio recalc
        self._log_step(5, "Recalcul portfolio", "OK", time.perf_counter() - t0, {})

    def _step6_quality(self):
        """Step 6: Generate quality report."""
        import time

        t0 = time.perf_counter()
        logger.info("Step 6: Quality report")
        # TODO: implement quality report
        self._log_step(6, "Rapport qualité", "OK", time.perf_counter() - t0, {})
