"""Tests of ``deweloperuch_mcp.usecases.get_developer``."""

from typing import Any

import pytest

from deweloperuch_mcp.models.developer_profile import DeveloperInvestment
from deweloperuch_mcp.models.errors import InvalidInputError, NotFoundError
from deweloperuch_mcp.models.values import (
    AreaM2,
    CitySlug,
    DeveloperCount,
    DeveloperSlug,
    InvestmentsLimit,
)
from deweloperuch_mcp.usecases.get_developer import GetDeveloper, GetDeveloperRequest
from deweloperuch_mcp.usecases.get_government_statistics import GetGovernmentStatisticsRequest
from deweloperuch_mcp.usecases.get_investment import GetInvestmentRequest
from deweloperuch_mcp.usecases.get_market_statistics import GetMarketStatisticsRequest
from deweloperuch_mcp.usecases.get_offer import GetOfferRequest
from support.fakes.catalogs import (
    DEVELOPER,
    EchoPageLinks,
    FakeCatalogs,
)


def project(slug: str, active: int | None) -> DeveloperInvestment:
    return DeveloperInvestment(
        investment_slug=slug,
        name=slug,
        city="Kraków",
        city_slug="krakow",
        status="active",
        active_offers=active,
        total_offers=None,
        avg_price=None,
        avg_area_m2=None,
        avg_price_per_m2=None,
        developer=DEVELOPER,
    )


def test_a_developer_is_one_request_with_its_links() -> None:
    fake = FakeCatalogs(projects=(project("a", 1), project("b", 5), project("c", 3)))

    found = GetDeveloper(fake, EchoPageLinks()).execute(
        GetDeveloperRequest(
            developer=DeveloperSlug("atal"), city=CitySlug("krakow"), limit=InvestmentsLimit(2)
        )
    )

    assert fake.calls == ["developer atal krakow"]
    assert [item.investment_slug for item in found.listing.investments] == ["b", "c"]
    assert (found.listing.omitted, found.hint) == (1, None)
    assert found.developer_url == "developer:krakow:atal"
    assert found.investment_urls == ("investment:b", "investment:c")


def test_a_developer_without_investments_in_a_city_points_to_the_whole_country() -> None:
    found = GetDeveloper(FakeCatalogs(), EchoPageLinks()).execute(
        GetDeveloperRequest(
            developer=DeveloperSlug("atal"), city=CitySlug("sopot"), limit=InvestmentsLimit(20)
        )
    )

    assert found.hint == (
        "Deweloper nie ma inwestycji z aktywnymi ofertami w 'sopot'. Spróbuj city=polska "
        "(cała Polska)."
    )


@pytest.mark.parametrize(
    ("city", "message"),
    [
        (
            "polska",
            "Nie znaleziono dewelopera 'nikt'. Slug dewelopera podaje search_developers (po "
            "nazwie) albo pole developer_slug w search_offers, get_investment i get_offer; city "
            "to city_slug z search_locations albo polska (cała Polska).",
        ),
        (
            "krakow",
            "Nie znaleziono dewelopera 'nikt' w 'krakow'. Slug dewelopera podaje "
            "search_developers (po nazwie) albo pole developer_slug w search_offers, "
            "get_investment i get_offer; city to city_slug z search_locations albo polska (cała "
            "Polska).",
        ),
    ],
)
def test_an_unknown_developer_says_where_slugs_come_from(city: str, message: str) -> None:
    fake = FakeCatalogs(errors={f"developer nikt {city}": NotFoundError("brak")})

    with pytest.raises(NotFoundError) as caught:
        GetDeveloper(fake, EchoPageLinks()).execute(
            GetDeveloperRequest(
                developer=DeveloperSlug("nikt"), city=CitySlug(city), limit=InvestmentsLimit(5)
            )
        )

    assert str(caught.value) == message


def test_the_market_and_developer_arguments_with_their_defaults() -> None:
    market = GetMarketStatisticsRequest.parse(city=" krakow ", area_max=60).criteria
    assert (market.city, market.price, market.top) == (CitySlug("krakow"), None, DeveloperCount(10))
    assert market.area is not None and market.area.high == AreaM2(60)
    assert GetDeveloperRequest.parse(developer_slug=" atal ") == GetDeveloperRequest(
        developer=DeveloperSlug("atal"),
        city=CitySlug("polska"),
        limit=InvestmentsLimit(20),
    )


@pytest.mark.parametrize(
    ("call", "first"),
    [
        (lambda: GetOfferRequest.parse(offer_id=0, investment_slug="SMOLNA"), "offer_id"),
        (
            lambda: GetInvestmentRequest.parse(
                investment_slug="Smolna", include_history="x", limit=-1
            ),
            "investment_",
        ),
        (
            lambda: GetInvestmentRequest.parse(
                investment_slug="smolna", include_history="x", limit=-1
            ),
            "include_",
        ),
        (
            lambda: GetGovernmentStatisticsRequest.parse(location="Kraków", dataset="x", periods=0),
            "location",
        ),
        (
            lambda: GetGovernmentStatisticsRequest.parse(location="polska", dataset="x", periods=0),
            "dataset",
        ),
        (lambda: GetMarketStatisticsRequest.parse(city="polska", price_min=-1), "city"),
        (
            lambda: GetMarketStatisticsRequest.parse(city="krakow", area_min=-1, top_developers=0),
            "area",
        ),
        (
            lambda: GetDeveloperRequest.parse(developer_slug="X", city="X", limit=0),
            "developer_slug",
        ),
        (lambda: GetDeveloperRequest.parse(developer_slug="atal", city="X", limit=0), "city"),
    ],
)
def test_the_other_operations_are_checked_in_order(call: Any, first: str) -> None:
    with pytest.raises(InvalidInputError, match=f"^{first}"):
        call()
