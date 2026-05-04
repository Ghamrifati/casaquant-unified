"""Tests for scraping quality guardrails."""

from app.domains.scraping.guardrails import validate_scrape_quality


class TestValidateScrapeQuality:
    def test_valid_data(self):
        records = [
            {"Valeur": "ATW", "Cours": "150,00", "Cours Réf": "148,00", "timestamp": "2026-05-04 14:00:00"}
            for _ in range(75)
        ]
        result = validate_scrape_quality(records)
        assert result["valid"] is True
        assert len(result["errors"]) == 0

    def test_too_few_tickers(self):
        records = [{"Valeur": "ATW", "Cours": "150,00"} for _ in range(10)]
        result = validate_scrape_quality(records)
        assert result["valid"] is False
        assert "Too few tickers" in result["errors"][0]

    def test_too_many_missing_prices(self):
        records = [{"Valeur": f"T{i}", "Cours": "-"} for i in range(75)]
        result = validate_scrape_quality(records)
        assert result["valid"] is False
        assert "missing" in result["errors"][0].lower()
