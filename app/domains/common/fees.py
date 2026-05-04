"""CasaQuant Unified — BVC transaction fees calculation.

Real BVC fees:
- Brokerage: 0.6% (min 10 MAD)
- Stock exchange tax: 0.1%
- VAT on brokerage: 10%
"""

from app.config import settings


def calculate_fees(
    amount: float,
    brokerage_rate: float | None = None,
    tax_rate: float | None = None,
    vat_rate: float | None = None,
    min_brokerage: float | None = None,
) -> dict:
    """Calculate BVC transaction fees for a given gross amount.

    Args:
        amount: Gross transaction amount in MAD.
        brokerage_rate: Custom brokerage rate (default from config).
        tax_rate: Custom tax rate (default from config).
        vat_rate: Custom VAT rate (default from config).
        min_brokerage: Minimum brokerage fee (default from config).

    Returns:
        Dict with breakdown: brokerage, tax, vat, total_fees, net_amount.
    """
    br = brokerage_rate if brokerage_rate is not None else settings.bvc_brokerage_rate
    tr = tax_rate if tax_rate is not None else settings.bvc_tax_rate
    vr = vat_rate if vat_rate is not None else settings.bvc_vat_rate
    min_br = min_brokerage if min_brokerage is not None else settings.bvc_min_brokerage

    brokerage = max(amount * br, min_br)
    tax = amount * tr
    vat = brokerage * vr
    total_fees = brokerage + tax + vat
    net_amount = amount + total_fees  # buyer pays gross + fees

    return {
        "gross_amount": round(amount, 2),
        "brokerage": round(brokerage, 2),
        "tax": round(tax, 2),
        "vat": round(vat, 2),
        "total_fees": round(total_fees, 2),
        "net_amount": round(net_amount, 2),
    }


def round_trip_fees(amount: float) -> dict:
    """Calculate round-trip (buy + sell) fees."""
    buy = calculate_fees(amount)
    sell = calculate_fees(amount)  # same rates on exit
    total = buy["total_fees"] + sell["total_fees"]
    return {
        "buy_fees": buy["total_fees"],
        "sell_fees": sell["total_fees"],
        "round_trip_fees": round(total, 2),
        "round_trip_pct": round(total / amount * 100, 3) if amount else 0.0,
    }
