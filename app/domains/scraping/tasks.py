"""CasaQuant Unified — Celery tasks for scraping and EOD pipeline."""

from celery import Celery

from app.config import settings

# Use Redis as broker and result backend
celery_app = Celery(
    "casaquant",
    broker=str(settings.redis_url),
    backend=str(settings.redis_url),
    include=[
        "app.domains.scraping.tasks",
        "app.domains.pipeline.tasks",
        "app.domains.backtest.tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Africa/Casablanca",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=300,  # 5 minutes max per task
    worker_prefetch_multiplier=1,
    beat_schedule={
        "scrape-intraday-09:15": {
            "task": "app.domains.scraping.tasks.scrape_intraday",
            "schedule": "cron",
            "args": (),
            "kwargs": {"hour": 9, "minute": 15},
        },
        "scrape-intraday-10:00": {
            "task": "app.domains.scraping.tasks.scrape_intraday",
            "schedule": "cron",
            "args": (),
            "kwargs": {"hour": 10, "minute": 0},
        },
        "scrape-intraday-11:00": {
            "task": "app.domains.scraping.tasks.scrape_intraday",
            "schedule": "cron",
            "args": (),
            "kwargs": {"hour": 11, "minute": 0},
        },
        "scrape-intraday-12:00": {
            "task": "app.domains.scraping.tasks.scrape_intraday",
            "schedule": "cron",
            "args": (),
            "kwargs": {"hour": 12, "minute": 0},
        },
        "scrape-intraday-13:00": {
            "task": "app.domains.scraping.tasks.scrape_intraday",
            "schedule": "cron",
            "args": (),
            "kwargs": {"hour": 13, "minute": 0},
        },
        "scrape-intraday-14:00": {
            "task": "app.domains.scraping.tasks.scrape_intraday",
            "schedule": "cron",
            "args": (),
            "kwargs": {"hour": 14, "minute": 0},
        },
        "scrape-intraday-15:00": {
            "task": "app.domains.scraping.tasks.scrape_intraday",
            "schedule": "cron",
            "args": (),
            "kwargs": {"hour": 15, "minute": 0},
        },
        "scrape-intraday-16:00": {
            "task": "app.domains.scraping.tasks.scrape_intraday",
            "schedule": "cron",
            "args": (),
            "kwargs": {"hour": 16, "minute": 0},
        },
        "transform-eod": {
            "task": "app.domains.scraping.tasks.transform_eod",
            "schedule": "cron",
            "args": (),
            "kwargs": {"hour": 16, "minute": 10},
        },
        "recalc-scoring": {
            "task": "app.domains.pipeline.tasks.run_recalc",
            "schedule": "cron",
            "args": (),
            "kwargs": {"hour": 16, "minute": 20},
        },
        "telegram-report": {
            "task": "app.domains.scraping.tasks.send_telegram_report",
            "schedule": "cron",
            "args": (),
            "kwargs": {"hour": 8, "minute": 30, "day_of_week": "mon-fri"},
        },
    },
)


@celery_app.task(bind=True, max_retries=3)
def scrape_intraday(self):
    """Scrape intraday BVC data."""
    # TODO: implement scraping logic
    return {"status": "ok", "message": "Intraday scraping stub"}


@celery_app.task(bind=True, max_retries=3)
def transform_eod(self):
    """Transform intraday snapshots into EOD features."""
    # TODO: implement EOD transformation
    return {"status": "ok", "message": "EOD transform stub"}


@celery_app.task(bind=True)
def send_telegram_report(self):
    """Send daily Telegram report."""
    # TODO: implement Telegram report
    return {"status": "ok", "message": "Telegram report stub"}
