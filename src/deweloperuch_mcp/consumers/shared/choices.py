"""Choices of the interfaces' parameters as ``Literal`` types, for typer's options and the
MCP input schemas (an enum would change the schemas).

Each is a projection of a domain value set, which stays the one source of truth: the
tests pin them equal (tests/unit/consumers/shared/test_choices.py).
"""

from typing import Literal

SortChoice = Literal[
    "price_asc",
    "price_desc",
    "price_per_m2_asc",
    "price_per_m2_desc",
    "area_asc",
    "area_desc",
    "biggest_drop",
]
"""``models.values.OfferSort``."""

StatusChoice = Literal["active", "archived", "all"]
"""``models.values.OfferStatus``."""

PageSizeChoice = Literal[10, 50, 100]
"""``models.values.PAGE_SIZES``."""

DEFAULT_PAGE_SIZE: PageSizeChoice = 10
"""``models.values.DEFAULT_PAGE_SIZE``, typed as a choice."""

DatasetChoice = Literal[
    "dwellings_quarterly",
    "dwellings_monthly",
    "average_area",
    "demography",
    "population",
    "unemployment",
    "wages",
    "nbp_prices",
]
"""``models.government_statistics.Dataset``."""

InvestmentSortChoice = Literal[
    "active_offers", "price_per_m2_asc", "price_per_m2_desc", "price_asc", "price_desc", "name"
]
"""``models.investment_summary.InvestmentSort``."""

GranularityChoice = Literal["month", "quarter"]
"""``models.transaction_series.Granularity``."""

DEFAULT_GRANULARITY: GranularityChoice = "month"
"""The granularity of ``get_transaction_statistics`` unless asked otherwise."""
