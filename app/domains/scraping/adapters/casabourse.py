"""CasaQuant Unified — Casabourse API adapter (primary source).

Fast (~2s), reliable. Falls back to Wafabourse HTML if unavailable.
"""

import logging
import math
from datetime import datetime
from decimal import Decimal
from typing import Any

from app.config import settings

logger = logging.getLogger("casaquant.scraping.casabourse")

# Expected columns from casabourse API
COLUMNS = [
    "Valeur", "Cours", "Var (%)", "Volume", "Qté",
    "Cours Réf", "Ouverture", "+ Haut", "+ Bas",
    "Meilleure demande", "Meilleure offre",
]


def safe_format(val: Any) -> str:
    """Format a value from casabourse DataFrame to string."""
    import pandas as pd
    if isinstance(val, list) and len(val) == 0:
        return "-"
    if pd.isna(val) or val is None or val == "":
        return "-"
    try:
        fval = float(val)
        if math.isnan(fval):
            return "-"
        return f"{fval:.2f}".replace(".", ",")
    except (ValueError, TypeError):
        return str(val)


def scrape_casabourse_api() -> list[dict]:
    """Fetch market data via casabourse package (fast primary source).

    Returns list of dicts matching COLUMNS + timestamp + seance.
    """
    records: list[dict] = []
    try:
        import casabourse as cb  # type: ignore[import-untyped]
        import pandas as pd  # type: ignore[import-untyped]

        logger.info("Fetching via casabourse.get_market_data()...")
        df = cb.get_market_data()

        if df is None or (hasattr(df, "empty") and df.empty):
            logger.warning("casabourse returned no data (timeout likely)")
            return records

        # Filter out obligations (names starting with digit) and rights ("DA ")
        df = df[~df["Nom"].str.match(r"^\d", na=False)]
        df = df[~df["Nom"].str.startswith("DA ", na=False)]
        logger.info("%d equities after filtering", len(df))

        now = datetime.now()
        seance = classify_session(now)

        for _, row in df.iterrows():
            record = {
                "Valeur": str(row.get("Nom", "-")).strip(),
                "Cours": safe_format(row.get("Cours courant")),
                "Var (%)": safe_format(row.get("Variation %")),
                "Volume": safe_format(row.get("Volume échangé")),
                "Qté": safe_format(row.get("Quantité échangée")),
                "Cours Réf": safe_format(row.get("Prix référence")),
                "Ouverture": safe_format(row.get("Ouverture")),
                "+ Haut": safe_format(row.get("Plus haut")),
                "+ Bas": safe_format(row.get("Plus bas")),
                "Meilleure demande": safe_format(row.get("Meilleur prix achat")),
                "Meilleure offre": safe_format(row.get("Meilleur prix vente")),
                "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
                "seance": seance,
            }
            records.append(record)

        logger.info("Primary source success: %d equities", len(records))

    except ImportError:
        logger.error("Package 'casabourse' or 'pandas' not installed")
    except (ValueError, KeyError, AttributeError, TypeError) as exc:
        logger.error("casabourse error: %s", exc)

    return records


def classify_session(now: datetime | None = None) -> str:
    """Classify BVC session by current time."""
    if now is None:
        now = datetime.now()
    total = now.hour * 60 + now.minute
    if total < 9 * 60 + 45:
        return "Ouverture"
    elif total < 10 * 60 + 30:
        return "Matin_1"
    elif total < 11 * 60 + 30:
        return "Matin_2"
    elif total < 12 * 60 + 30:
        return "Midi_1"
    elif total < 13 * 60 + 30:
        return "Midi_2"
    elif total < 14 * 60 + 30:
        return "ApresMidi"
    elif total < 15 * 60 + 30:
        return "PreCloture"
    return "Cloture"
