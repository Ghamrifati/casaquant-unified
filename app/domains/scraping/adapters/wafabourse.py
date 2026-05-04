"""CasaQuant Unified — Wafabourse HTML adapter (fallback via Playwright).

Slow (~30s) but reliable fallback when casabourse API is down.
"""

import logging
import time
from datetime import datetime
from decimal import Decimal

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import sync_playwright

from app.config import settings

logger = logging.getLogger("casaquant.scraping.wafabourse")

URL = "https://www.wafabourse.com/fr/market-tracking/instruments-financiers"

COLUMNS = [
    "Valeur", "Cours", "Var (%)", "Volume", "Qté",
    "Cours Réf", "Ouverture", "+ Haut", "+ Bas",
    "Meilleure demande", "Meilleure offre",
]


def _parse_decimal(val: str) -> Decimal | None:
    """Parse French-formatted number (1 234,56 -> 1234.56)."""
    if not val or val.strip() in ("-", ""):
        return None
    cleaned = val.replace("\u202f", "").replace("\xa0", "").replace(" ", "").replace(",", ".")
    try:
        return Decimal(cleaned)
    except Exception:
        return None


def _retry_with_backoff(max_retries: int, base_delay: float, func):
    """Execute func with exponential backoff retries."""
    for attempt in range(1, max_retries + 1):
        try:
            return func()
        except (PlaywrightError, PlaywrightTimeout, RuntimeError, OSError, ValueError) as exc:
            if attempt == max_retries:
                logger.error("Failed after %d attempts: %s", max_retries, exc)
                raise
            delay = base_delay * (2 ** (attempt - 1))
            logger.warning("Attempt %d/%d failed — retry in %.0fs: %s", attempt, max_retries, delay, exc)
            time.sleep(delay)
    return None


def scrape_wafabourse_html() -> list[dict]:
    """Scrape Wafabourse HTML table via Playwright."""
    return _retry_with_backoff(
        max_retries=settings.scraper_max_retries,
        base_delay=5.0,
        func=_scrape,
    )


def _scrape() -> list[dict]:
    records: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="fr-FR",
            viewport={"width": 1920, "height": 1080},
        )
        page = context.new_page()

        try:
            logger.info("Navigating to %s", URL)
            response = page.goto(URL, wait_until="networkidle", timeout=settings.scraper_timeout * 1000)

            if response and response.status >= 400:
                raise RuntimeError(f"HTTP {response.status} — site unavailable")

            # Wait for table to populate
            page.wait_for_timeout(8000)
            try:
                page.wait_for_function(
                    """() => {
                        const rows = document.querySelectorAll('table tbody tr');
                        return rows.length > 1 ||
                               (rows.length === 1 && !rows[0].innerText.includes('Aucune donnée'));
                    }""",
                    timeout=15_000,
                )
            except PlaywrightTimeout:
                logger.warning("Timeout waiting for data — market may be closed")

            # Scroll to reveal all rows
            _scroll_table(page)

            # Extract rows
            rows = page.query_selector_all("table tbody tr")
            now = datetime.now()
            seance = classify_session(now)

            for row in rows:
                cells = row.query_selector_all("td")
                if not cells:
                    continue
                texts = [c.inner_text().strip() for c in cells]

                if len(texts) == 1 or "Aucune donnée" in texts[0]:
                    continue

                while len(texts) < len(COLUMNS):
                    texts.append("")

                record = dict(zip(COLUMNS, texts[:len(COLUMNS)]))
                record["timestamp"] = now.strftime("%Y-%m-%d %H:%M:%S")
                record["seance"] = seance
                records.append(record)

            logger.info("Extracted %d equities from Wafabourse", len(records))

        except PlaywrightTimeout:
            logger.error("Timeout loading page")
        except (OSError, RuntimeError) as exc:
            logger.error("Wafabourse error: %s", exc, exc_info=True)
        finally:
            browser.close()

    return records


def _scroll_table(page) -> None:
    """Progressively scroll the table container to reveal all rows."""
    scroll_selector = page.evaluate("""
        () => {
            const candidates = [
                '.dataTables_scrollBody',
                '[class*="scrollBody"]',
                '[class*="table-container"]',
                'div[style*="overflow"]',
                'div[style*="height"]',
            ];
            for (const sel of candidates) {
                const el = document.querySelector(sel);
                if (el && el.scrollHeight > el.clientHeight) return sel;
            }
            const table = document.querySelector('table');
            if (table) {
                let el = table.parentElement;
                while (el) {
                    if (el.scrollHeight > el.clientHeight + 10) {
                        el.setAttribute('data-scroll-target', 'true');
                        return '[data-scroll-target="true"]';
                    }
                    el = el.parentElement;
                }
            }
            return null;
        }
    """)

    logger.info("Scrollable container detected: %s", scroll_selector)

    max_iter = 100
    prev_count = 0
    stable = 0

    for i in range(max_iter):
        cur_count = page.evaluate(
            "() => document.querySelectorAll('table tbody tr').length"
        )
        if cur_count == prev_count:
            stable += 1
            if stable >= 4:
                logger.info("Stable at %d rows after %d iterations", cur_count, i + 1)
                break
        else:
            stable = 0
            prev_count = cur_count

        page.evaluate(
            """(sel) => {
                if (sel) {
                    const t = document.querySelector(sel);
                    if (t) t.scrollTop += 400;
                }
                window.scrollBy(0, 400);
                document.querySelectorAll('div').forEach(d => {
                    if (d.scrollHeight > d.clientHeight + 50) d.scrollTop += 400;
                });
            }""",
            scroll_selector,
        )
        page.wait_for_timeout(300)

    # Final scroll
    page.evaluate("""
        () => {
            document.querySelectorAll('div').forEach(div => {
                if (div.scrollHeight > div.clientHeight + 50) {
                    div.scrollTop = div.scrollHeight;
                }
            });
            window.scrollTo(0, document.body.scrollHeight);
        }
    """)
    page.wait_for_timeout(1000)


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
