"""CasaQuant Unified — Celery tasks for backtest execution."""

import logging

from app.domains.scraping.tasks import celery_app

logger = logging.getLogger("casaquant.backtest.tasks")


@celery_app.task(bind=True, max_retries=1, time_limit=600)
def run_backtest_for_ticker(self, ticker_id: int, strategy: str = "v4"):
    """Run a single-ticker backtest asynchronously.

    Args:
        ticker_id: Database ticker ID.
        strategy: 'v4' or 'v7'.
    """
    logger.info("Running backtest: ticker_id=%s strategy=%s", ticker_id, strategy)
    # TODO: implement
    return {"ticker_id": ticker_id, "strategy": strategy, "status": "ok"}
