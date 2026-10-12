"""Choices of the interfaces' parameters as ``Literal`` types, for typer's options and the
MCP input schemas (an enum would change the schemas).

Each is a projection of a domain value set, which stays the one source of truth: the
tests pin them equal (tests/test_cli.py, tests/test_mcp_server.py).
"""

from typing import Literal

SortChoice = Literal["price_asc", "price_desc"]
"""``domain.values.OfferSort``."""

PageSizeChoice = Literal[10, 50, 100]
"""``domain.values.PAGE_SIZES``."""

DEFAULT_PAGE_SIZE: PageSizeChoice = 10
"""``domain.values.DEFAULT_PAGE_SIZE``, typed as a choice."""

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
"""``domain.statistics.Dataset``."""
