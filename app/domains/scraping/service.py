"""CasaQuant Unified — Scraping orchestration service.

Encapsulates the full ingestion pipeline:
1. Try casabourse API (primary)
2. Validate quality
3. Fall back to Wafabourse HTML if needed
4. Store snapshots in DB
"""

import logging
from datetime import datetime
from decimal import Decimal

from sqlmodel import Session

from app.config import settings
from app.domains.market.models import MarketSnapshot
from app.domains.scraping.adapters import casabourse, wafabourse
from app.domains.scraping.guardrails import validate_scrape_quality
from app.domains.scraping.repository import bulk_insert_snapshots, get_or_create_tickers, log_ingestion

logger = logging.getLogger("casaquant.scraping.service")


def run_ingestion(session: Session) -> dict:
    """Run full ingestion pipeline and store results.

    Returns summary dict with source, count, and status.
    """
    logger.info("=" * 55)
    logger.info("  INGESTION  |  %s", datetime.now().strftime("%Y-%m-%d %H:%M"))
    logger.info("=" * 55)

    source = "none"
    records: list[dict] = []

    # Primary source
    records = casabourse.scrape_casabourse_api()
    if records:
        quality = validate_scrape_quality(records)
        if quality["valid"]:
            source = "casabourse_api"
        else:
            logger.warning("Casabourse quality insufficient: %s", quality["errors"])
            records = []

    # Fallback to Wafabourse
    if len(records) < 70:  # expected ~74 tickers
        logger.warning("Casabourse incomplete (%d/74) — trying Wafabourse HTML...", len(records))
        try:
            fallback = wafabourse.scrape_wafabourse_html()
            if len(fallback) > len(records):
                quality = validate_scrape_quality(fallback)
                if quality["valid"]:
                    records = fallback
                    source = "wafabourse_html"
                else:
                    logger.warning("Wafabourse quality insufficient: %s", quality["errors"])
        except (OSError, RuntimeError) as exc:
            logger.warning("Wafabourse crash: %s", exc)

    if not records:
        log_ingestion(session, source, 0, "error", "No data from any source")
        return {"status": "error", "source": source, "count": 0}

    # Resolve tickers
    names = {r["Valeur"] for r in records}
    ticker_map = get_or_create_tickers(session, names)

    # Build snapshots
    now = datetime.now()
    snapshots = []
    for rec in records:
        name = rec["Valeur"]
        ticker_id = ticker_map.get(name)
        if not ticker_id:
            continue

        snap = MarketSnapshot(
            ticker_id=ticker_id,
            session_time=now,
            price=_parse_price(rec.get("Cours")),
            volume=_parse_int(rec.get("Volume")),
            bid=_parse_price(rec.get("Meilleure demande")),
            ask=_parse_price(rec.get("Meilleure offre")),
            source=source,
        )
        snapshots.append(snap)

    inserted = bulk_insert_snapshots(session, snapshots)
    log_ingestion(session, source, inserted, "success")

    logger.info("Extracted: %d | Source: %s | Inserted: %d", len(records), source, inserted)
    return {"status": "success", "source": source, "count": inserted}


def _parse_price(val: str | None) -> Decimal | None:
    if not val or val.strip() in ("-", ""):
        return None
    cleaned = val.replace(" ", "").replace(",", ".").replace("\u202f", "").replace("\xa0", "")
    try:
        return Decimal(cleaned)
    except Exception:
        return None


def _parse_int(val: str | None) -> int | None:
    if not val or val.strip() in ("-", ""):
        return None
    cleaned = val.replace(" ", "").replace(",", "").replace("\u202f", "").replace("\xa0", "")
    try:
        return int(cleaned)
    except Exception:
        return None
