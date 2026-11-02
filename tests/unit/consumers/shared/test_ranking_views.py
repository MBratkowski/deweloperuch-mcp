"""Tests of ``deweloperuch_mcp.consumers.shared.ranking_views``."""

from typing import get_args

import pytest

from deweloperuch_mcp.consumers.shared import ranking_views as views
from deweloperuch_mcp.models.indicator_ranking import Indicator, IndicatorCriteria, IndicatorRanking
from deweloperuch_mcp.models.location_ranking import (
    LocationRanking,
    RankingLevel,
    RankingMarket,
    RankingOrder,
)
from deweloperuch_mcp.usecases.rank_locations import RankLocationsResult
from support.builders.rankings import criteria
from support.fakes.rankings import CITIES, NBP_PRICES, POWIATS

# The MCP server runs behind the SDK's in-memory client: its event loop needs Unix sockets.
pytestmark = pytest.mark.usefixtures("unix_sockets_for_the_event_loop")


def test_the_choices_are_the_domains() -> None:
    assert get_args(views.RankingLevelChoice) == tuple(level.value for level in RankingLevel)
    assert get_args(views.RankingSortChoice) == tuple(order.value for order in RankingOrder)
    assert get_args(views.RankingMarketChoice) == tuple(market.value for market in RankingMarket)
    assert get_args(views.IndicatorChoice) == tuple(indicator.value for indicator in Indicator)


def test_a_powiat_ranking_shows_its_market_and_period() -> None:
    ranking = LocationRanking.of(
        criteria(level=RankingLevel.POWIAT), POWIATS.on(RankingMarket.SECONDARY)
    )

    view = views.LocationRankingView.from_result(
        RankLocationsResult(ranking=ranking, period=POWIATS.period)
    )

    assert (view.market, view.period_start, view.period_end) == (
        "secondary",
        "2025-11-01",
        "2026-10",
    )
    assert (view.indicator, view.unit, view.period) == (None, None, None)
    assert view.items[0].powiat_id == 302


def test_a_city_ranking_shows_no_market() -> None:
    ranking = LocationRanking.of(criteria(), CITIES)

    view = views.LocationRankingView.from_result(RankLocationsResult(ranking=ranking))

    assert (view.market, view.period_start, view.period_end) == (None, None, None)


def test_an_indicator_ranking_shows_values_units_and_pages() -> None:
    ranking = IndicatorRanking.of(IndicatorCriteria(Indicator.NBP_PRICE_PER_M2), NBP_PRICES)
    urls = tuple(f"<strona {index}>" for index in range(ranking.returned))

    view = views.LocationRankingView.from_result(
        RankLocationsResult(ranking=ranking, without_data=49, stats_urls=urls)
    )

    assert (view.level, view.sort, view.indicator, view.unit, view.period) == (
        "city",
        "value_desc",
        "nbp_price_per_m2",
        "PLN/m²",
        "2026-Q2",
    )
    assert view.min_transactions is None and view.ranking_url is None
    first = view.items[0]
    assert (first.city_slug, first.value, first.stats_url) == ("warszawa", 16723.0, "<strona 0>")
    assert first.transaction_count is None
