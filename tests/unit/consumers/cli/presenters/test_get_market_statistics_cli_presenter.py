"""Tests of
``deweloperuch_mcp.consumers.cli.presenters.get_market_statistics_cli_presenter``.
"""

import dataclasses

import pytest

from deweloperuch_mcp.consumers.cli.presenters.get_market_statistics_cli_presenter import (
    GetMarketStatisticsCliPresenter,
)
from deweloperuch_mcp.models.market_statistics import CityOffers, MarketCriteria
from deweloperuch_mcp.usecases.get_market_statistics import GetMarketStatisticsResult
from support.builders.market import KRAKOW, OFFERS


def printed(offers: CityOffers, capsys: pytest.CaptureFixture[str]) -> list[str]:
    statistics = offers.statistics(MarketCriteria(city=KRAKOW))
    result = GetMarketStatisticsResult(
        statistics=statistics, list_url=None, developer_urls=(None,) * 3
    )
    GetMarketStatisticsCliPresenter(as_json=False).present(result)
    return capsys.readouterr().out.splitlines()


@pytest.mark.parametrize(
    ("offers", "head"),
    [
        (
            OFFERS,
            "Rynek ofert [krakow] · aktywne oferty: 8 · inwestycje: 4 · deweloperzy: 3 · stan "
            "na 2026-10-31.",
        ),
        (
            CityOffers(city=KRAKOW, offers=OFFERS.offers),
            "Rynek ofert [krakow] · aktywne oferty: 8 · inwestycje: 4 · deweloperzy: 3.",
        ),
    ],
)
def test_the_head_line_names_the_day_of_the_offers_when_known(
    offers: CityOffers, head: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert printed(offers, capsys)[0] == head


def test_a_top_developer_is_shown_by_its_name_and_slug_or_its_slug_alone(
    capsys: pytest.CaptureFixture[str],
) -> None:
    unnamed = tuple(
        dataclasses.replace(offer, developer_name=None) if offer.developer_slug == "dom" else offer
        for offer in OFFERS.offers
    )

    lines = printed(CityOffers(city=KRAKOW, offers=unnamed), capsys)

    assert [line for line in lines if " · oferty " in line] == [
        "  YIT Development [yit] · oferty 3 · inwestycje 1 · mediana 10 000 PLN/m²",
        "  ATAL S.A. [atal] · oferty 2 · inwestycje 2 · mediana 10 000 PLN/m²",
        "  dom · oferty 2 · inwestycje 1 · mediana 15 000 PLN/m²",
    ]
