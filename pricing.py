"""Palmertech pricing utilities for consistent investment calculations."""

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

BASE_RATE = Decimal("25.00")  # £/hr starting rate
START_YEAR = 2025  # Adjust to the project start year when the policy begins
BASE_APP_FEE = Decimal("25.00")  # £ base retainer for an app or site
PER_PAGE_FEE = Decimal("10.00")  # £ maintenance per produced or maintained page
MAX_RATE = Decimal("40.00")  # £ cap until manual review
FIRST_YEAR_INCREASE = Decimal("1.05")
SUBSEQUENT_INCREASE = Decimal("1.10")


def _quantise(value: Decimal) -> Decimal:
    """Return the value rounded to two decimal places using half-up rounding."""

    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def current_rate(reference_date: date | None = None) -> Decimal:
    """Return the current hourly development rate with annual increases applied."""

    today = reference_date or date.today()
    years_elapsed = max(0, today.year - START_YEAR)

    if years_elapsed == 0:
        return _quantise(BASE_RATE)

    if years_elapsed == 1:
        return _quantise(BASE_RATE * FIRST_YEAR_INCREASE)

    # Apply 10% compound increases year-on-year after the second year until capped.
    rate = BASE_RATE * SUBSEQUENT_INCREASE
    remaining_years = years_elapsed - 1
    for _ in range(1, remaining_years):
        rate *= SUBSEQUENT_INCREASE
        if rate >= MAX_RATE:
            return _quantise(MAX_RATE)

    return _quantise(rate if rate <= MAX_RATE else MAX_RATE)


def maintenance_cost(page_count: int) -> Decimal:
    """Calculate maintenance cost based on the base app fee plus per-page fee."""

    if page_count < 0:
        raise ValueError("page_count cannot be negative")

    total = BASE_APP_FEE + (PER_PAGE_FEE * Decimal(page_count))
    return _quantise(total)


def format_currency(value: Decimal | float | int | str) -> str:
    """Return a currency-formatted string for the supplied value."""

    decimal_value = Decimal(str(value))
    return f"£{_quantise(decimal_value):.2f}"


def pricing_summary(page_count: int) -> dict[str, str | int]:
    """Return a human-readable summary of the current pricing model."""

    rate = current_rate()
    maintenance = maintenance_cost(page_count)
    return {
        "current_rate": f"£{rate:.2f}/hour",
        "maintenance_cost": f"£{maintenance:.2f} total",
        "pages": page_count,
        "base_app_fee": f"£{BASE_APP_FEE:.2f}",
        "per_page_fee": f"£{PER_PAGE_FEE:.2f}/page",
        "annual_increase": "+5% after year 1, +10% compounded thereafter (capped at £40/hr)",
    }


__all__ = [
    "BASE_RATE",
    "BASE_APP_FEE",
    "PER_PAGE_FEE",
    "MAX_RATE",
    "current_rate",
    "maintenance_cost",
    "format_currency",
    "pricing_summary",
]
