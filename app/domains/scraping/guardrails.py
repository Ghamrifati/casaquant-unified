"""CasaQuant Unified — Data quality guardrails for scraping.

Validates scraped data before acceptance into the database.
"""

import logging
from datetime import datetime

logger = logging.getLogger("casaquant.scraping.guardrails")

EXPECTED_TICKERS = 70
MAX_VARIATION_PCT = 15.0
MAX_MISSING_PCT = 0.05


def validate_scrape_quality(records: list[dict]) -> dict:
    """Validate scraped records for quality.

    Returns dict with keys:
      - valid: bool
      - errors: list[str]
      - warnings: list[str]
    """
    errors = []
    warnings = []

    # Check count
    if len(records) < EXPECTED_TICKERS:
        errors.append(f"Too few tickers: {len(records)} < {EXPECTED_TICKERS}")

    # Check missing values
    missing = sum(1 for r in records if not r.get("Cours") or r["Cours"] in ("-", ""))
    missing_pct = missing / len(records) if records else 0
    if missing_pct > MAX_MISSING_PCT:
        errors.append(f"Too many missing prices: {missing_pct:.1%} > {MAX_MISSING_PCT:.1%}")

    # Check price variation
    total_var = 0
    for rec in records:
        try:
            cours = float(str(rec.get("Cours", "0")).replace(",", ".").replace(" ", ""))
            ref = float(str(rec.get("Cours Réf", "0")).replace(",", ".").replace(" ", ""))
            if ref > 0:
                var = abs((cours - ref) / ref) * 100
                total_var += var
        except (ValueError, TypeError):
            pass

    avg_var = total_var / len(records) if records else 0
    if avg_var > MAX_VARIATION_PCT:
        warnings.append(f"High avg variation: {avg_var:.1f}% > {MAX_VARIATION_PCT}%")

    # Check stale data (timestamp older than 5 minutes)
    now = datetime.now()
    stale = 0
    for rec in records:
        ts_str = rec.get("timestamp")
        if ts_str:
            try:
                ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S")
                if (now - ts).total_seconds() > 300:
                    stale += 1
            except ValueError:
                pass

    if stale > len(records) * 0.5:
        warnings.append(f"Stale data: {stale}/{len(records)} records > 5min old")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
    }
