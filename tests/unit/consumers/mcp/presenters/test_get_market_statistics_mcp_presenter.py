"""Tests of
``deweloperuch_mcp.consumers.mcp.presenters.get_market_statistics_mcp_presenter``.
"""

import dataclasses

from deweloperuch_mcp.consumers.mcp.presenters.get_market_statistics_mcp_presenter import (
    GetMarketStatisticsMcpPresenter,
)
from deweloperuch_mcp.consumers.mcp.support.mcp_model import dump
from deweloperuch_mcp.models.market_statistics import CityOffers, MarketCriteria
from deweloperuch_mcp.usecases.get_market_statistics import GetMarketStatisticsResult
from support.builders.market import KRAKOW, OFFERS


def summary(offers: CityOffers) -> GetMarketStatisticsResult:
    statistics = offers.statistics(MarketCriteria(city=KRAKOW))
    return GetMarketStatisticsResult(
        statistics=statistics, list_url=None, developer_urls=(None,) * 3
    )


def test_the_summary_names_the_day_of_its_offers_when_the_source_gives_one() -> None:
    dated = dump(GetMarketStatisticsMcpPresenter().present(summary(OFFERS)))
    undated = dump(
        GetMarketStatisticsMcpPresenter().present(
            summary(CityOffers(city=KRAKOW, offers=OFFERS.offers))
        )
    )

    assert list(dated)[:3] == ["city_slug", "as_of", "offers"]
    assert dated["as_of"] == "2026-10-31"
    assert "as_of" not in undated and undated["offers"] == dated["offers"] == 8


def test_a_top_developer_is_named_after_its_slug_and_without_a_name_has_none() -> None:
    unnamed = tuple(
        dataclasses.replace(offer, developer_name=None) if offer.developer_slug == "dom" else offer
        for offer in OFFERS.offers
    )

    shown = dump(
        GetMarketStatisticsMcpPresenter().present(summary(CityOffers(city=KRAKOW, offers=unnamed)))
    )

    top = shown["top_developers"]
    assert list(top[0])[:2] == ["developer_slug", "developer_name"]
    assert [share.get("developer_name") for share in top] == [
        "YIT Development",
        "ATAL S.A.",
        None,
    ]
    assert "developer_name" not in top[2]
