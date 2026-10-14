"""Every golden case of the MCP, one module per operation."""

from support.golden.mcp import Case
from support.golden.mcp_cases import (
    estimate_property_value,
    get_building,
    get_developer,
    get_government_statistics,
    get_investment,
    get_market_statistics,
    get_offer,
    get_transaction_statistics,
    rank_locations,
    search_developers,
    search_investments,
    search_locations,
    search_offers,
    stop,
)

CASES: dict[str, Case] = {
    **estimate_property_value.CASES,
    **get_building.CASES,
    **get_developer.CASES,
    **get_government_statistics.CASES,
    **get_investment.CASES,
    **get_market_statistics.CASES,
    **get_offer.CASES,
    **get_transaction_statistics.CASES,
    **rank_locations.CASES,
    **search_developers.CASES,
    **search_investments.CASES,
    **search_locations.CASES,
    **search_offers.CASES,
    **stop.CASES,
}
