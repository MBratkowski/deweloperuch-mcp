"""Tests of ``deweloperuch_mcp.usecases.support.arguments``."""

from collections.abc import Callable
from typing import Any

import pytest

from deweloperuch_mcp.models.errors import InvalidInputError, InvalidValueError, ValueName
from deweloperuch_mcp.models.government_statistics import Dataset
from deweloperuch_mcp.models.market_statistics import MarketCriteria
from deweloperuch_mcp.models.offer import OfferSearchCriteria
from deweloperuch_mcp.models.values import (
    AmountPln,
    AreaM2,
    CitySlug,
    DeveloperCount,
    DeveloperSlug,
    DistrictName,
    InvestmentsLimit,
    InvestmentSlug,
    LocationSlug,
    OfferId,
    OffersLimit,
    OfferSort,
    OfferStatus,
    PageNumber,
    PageSize,
    PricePerM2Pln,
)
from deweloperuch_mcp.usecases.get_developer import GetDeveloperRequest
from deweloperuch_mcp.usecases.get_government_statistics import GetGovernmentStatisticsRequest
from deweloperuch_mcp.usecases.get_investment import GetInvestmentRequest
from deweloperuch_mcp.usecases.get_market_statistics import GetMarketStatisticsRequest
from deweloperuch_mcp.usecases.get_offer import GetOfferRequest
from deweloperuch_mcp.usecases.search_locations import SearchLocationsRequest
from deweloperuch_mcp.usecases.search_offers import SearchOffersRequest
from deweloperuch_mcp.usecases.support import arguments

LOCATION_HELP = (
    "location: oczekiwano polska, agregat (7-miast, 10-miast, 6-miast-bez-warszawy) albo "
    "slug miasta bez polskich znaków, np. warszawa, krakow, jastrzebie (Jastrzębie-Zdrój); "
)


REFUSALS: list[tuple[str, Any, str]] = [
    (
        "query",
        lambda: SearchLocationsRequest.parse(query=" k "),
        "query: podaj od 2 do 100 znaków nazwy miasta, dzielnicy lub ulicy, podano ' k '.",
    ),
    (
        "city",
        lambda: SearchOffersRequest.parse(city=" Kraków ").criteria,
        "city: oczekiwano slug miasta (np. warszawa) albo polska; slug podaje "
        "search_locations; podano ' Kraków '.",
    ),
    (
        "price_min",
        lambda: SearchOffersRequest.parse(city="warszawa", price_min=-1).criteria,
        "price_min musi być liczbą całkowitą z zakresu 0–99999999 (PLN), podano -1.",
    ),
    (
        "price_max",
        lambda: SearchOffersRequest.parse(city="warszawa", price_max=100_000_000).criteria,
        "price_max musi być liczbą całkowitą z zakresu 0–99999999 (PLN), podano 100000000.",
    ),
    (
        "price order",
        lambda: SearchOffersRequest.parse(city="warszawa", price_min=7, price_max=5).criteria,
        "price_min (7) jest większe niż price_max (5); zamień je miejscami.",
    ),
    (
        "area_min",
        lambda: SearchOffersRequest.parse(city="warszawa", area_min=40.5).criteria,
        "area_min musi być liczbą całkowitą z zakresu 0–9999 (m²), podano 40.5.",
    ),
    (
        "area_max",
        lambda: SearchOffersRequest.parse(city="warszawa", area_max="60").criteria,
        "area_max musi być liczbą całkowitą z zakresu 0–9999 (m²), podano '60'.",
    ),
    (
        "area order",
        lambda: SearchOffersRequest.parse(city="warszawa", area_min=60, area_max=40).criteria,
        "area_min (60) jest większe niż area_max (40); zamień je miejscami.",
    ),
    (
        "sort",
        lambda: SearchOffersRequest.parse(city="warszawa", sort="amount").criteria,
        "sort musi być jedną z wartości price_asc, price_desc, price_per_m2_asc, "
        "price_per_m2_desc, area_asc, area_desc, biggest_drop albo pusty (domyślna kolejność "
        "serwisu), podano 'amount'.",
    ),
    (
        "price_per_m2_min",
        lambda: SearchOffersRequest.parse(city="warszawa", price_per_m2_min=1_000_000).criteria,
        "price_per_m2_min musi być liczbą całkowitą z zakresu 0–999999 (PLN/m²), podano 1000000.",
    ),
    (
        "price_per_m2 order",
        lambda: (
            SearchOffersRequest.parse(
                city="warszawa", price_per_m2_min=9, price_per_m2_max=8
            ).criteria
        ),
        "price_per_m2_min (9) jest większe niż price_per_m2_max (8); zamień je miejscami.",
    ),
    (
        "district",
        lambda: SearchOffersRequest.parse(city="warszawa", district=" M ").criteria,
        "district: podaj nazwę dzielnicy (od 2 do 100 znaków) tak, jak zwraca ją "
        "search_locations (kind=district), np. Mokotów; podano ' M '.",
    ),
    (
        "district not text",
        lambda: SearchOffersRequest.parse(city="warszawa", district=7).criteria,
        "district: podaj nazwę dzielnicy (od 2 do 100 znaków) tak, jak zwraca ją "
        "search_locations (kind=district), np. Mokotów; podano 7.",
    ),
    (
        "district of the whole country",
        lambda: SearchOffersRequest.parse(city="polska", district="Mokotów").criteria,
        "district działa tylko z jednym miastem: podaj jako city slug miasta tej dzielnicy "
        "(search_locations zwraca go przy dzielnicy), a nie polska; podano 'Mokotów'.",
    ),
    (
        "price_dropped",
        lambda: SearchOffersRequest.parse(city="warszawa", price_dropped="yes").criteria,
        "price_dropped musi być true albo false, podano 'yes'.",
    ),
    (
        "status",
        lambda: SearchOffersRequest.parse(city="warszawa", status="sold").criteria,
        "status musi być jedną z wartości active, archived, all, podano 'sold'.",
    ),
    (
        "market city",
        lambda: GetMarketStatisticsRequest.parse(city="polska"),
        "city: statystyki rynku są tylko dla jednego miasta; podaj city_slug miasta z "
        "search_locations (np. warszawa), a nie polska; podano 'polska'.",
    ),
    (
        "top_developers",
        lambda: GetMarketStatisticsRequest.parse(city="krakow", top_developers=0),
        "top_developers musi być liczbą całkowitą z zakresu 1–30 (liczba deweloperów w "
        "wyniku), podano 0.",
    ),
    (
        "developer_slug",
        lambda: GetDeveloperRequest.parse(developer_slug="ATAL"),
        "developer_slug: oczekiwano slug dewelopera, np. atal; podają go search_developers, "
        "search_offers i search_investments (developer_slug); podano 'ATAL'.",
    ),
    (
        "developer limit",
        lambda: GetDeveloperRequest.parse(developer_slug="atal", limit=0),
        "limit musi być liczbą całkowitą z zakresu 1–1000 (liczba inwestycji w wyniku), podano 0.",
    ),
    (
        "page",
        lambda: SearchOffersRequest.parse(city="warszawa", page=21).criteria,
        "page musi być liczbą całkowitą z zakresu 1–20 (serwis ma najwyżej 20 stron), podano 21.",
    ),
    (
        "per_page",
        lambda: SearchOffersRequest.parse(city="warszawa", per_page=20).criteria,
        "per_page musi być jedną z wartości 10, 50, 100 (inne serwis zamienia na 10), podano 20.",
    ),
    (
        "offer_id",
        lambda: GetOfferRequest.parse(offer_id=0, investment_slug="smolna"),
        "offer_id musi być liczbą całkowitą z zakresu 1–9223372036854775807 (identyfikator "
        "oferty z search_offers), podano 0.",
    ),
    (
        "investment_slug",
        lambda: GetInvestmentRequest.parse(investment_slug="Smolna"),
        "investment_slug: oczekiwano slug inwestycji, np. smolna; podaje go search_offers "
        "(investment_slug); podano 'Smolna'.",
    ),
    (
        "include_history",
        lambda: GetInvestmentRequest.parse(investment_slug="smolna", include_history="yes"),
        "include_history musi być true albo false, podano 'yes'.",
    ),
    (
        "limit",
        lambda: GetInvestmentRequest.parse(investment_slug="smolna", limit=-1),
        "limit musi być liczbą całkowitą z zakresu 0–100000 (liczba ofert w wyniku), podano -1.",
    ),
    (
        # The statistics' location repeats the trimmed text (as it always did).
        "location",
        lambda: GetGovernmentStatisticsRequest.parse(location=" Kraków ", dataset="wages"),
        LOCATION_HELP + "podano 'Kraków'.",
    ),
    (
        "location not text",
        lambda: GetGovernmentStatisticsRequest.parse(location=7, dataset="wages"),
        LOCATION_HELP + "podano 7.",
    ),
    (
        "dataset",
        lambda: GetGovernmentStatisticsRequest.parse(location="polska", dataset="prices"),
        "dataset musi być jedną z wartości dwellings_quarterly, dwellings_monthly, "
        "average_area, demography, population, unemployment, wages, nbp_prices, podano "
        "'prices'.",
    ),
    (
        "periods",
        lambda: GetGovernmentStatisticsRequest.parse(
            location="polska", dataset="wages", periods=True
        ),
        "periods musi być liczbą całkowitą z zakresu 1–1000 (liczba ostatnich okresów), "
        "podano True.",
    ),
]


REFUSED: list[Callable[[], object]] = [
    lambda: CitySlug("X"),
    lambda: InvestmentSlug("X"),
    lambda: LocationSlug("X"),
    lambda: OfferId(0),
    lambda: AmountPln(-1),
    lambda: AreaM2(-1),
    lambda: PageNumber(0),
    lambda: PageSize(7),
    lambda: OffersLimit(-1),
    lambda: OfferSort.parse("x"),
    lambda: Dataset.parse("x"),
    lambda: DeveloperSlug("X"),
    lambda: PricePerM2Pln(-1),
    lambda: DistrictName("\x1b"),
    lambda: OfferStatus.parse("x"),
    lambda: InvestmentsLimit(0),
    lambda: DeveloperCount(31),
    lambda: MarketCriteria(city=CitySlug("polska")),
    lambda: OfferSearchCriteria(city=CitySlug("polska"), district=DistrictName("Wola")),
]


@pytest.mark.parametrize(("parameter", "call", "message"), REFUSALS, ids=[r[0] for r in REFUSALS])
def test_a_refusal_names_the_parameter_and_what_to_give(
    parameter: str, call: Any, message: str
) -> None:
    with pytest.raises(InvalidInputError) as caught:
        call()

    assert str(caught.value) == message
    assert not isinstance(caught.value, InvalidValueError)  # worded for the caller
    assert isinstance(caught.value.__cause__, InvalidValueError)  # the domain's refusal


def test_every_value_of_the_domain_has_a_parameter() -> None:
    assert set(arguments.PARAMETERS) == set(ValueName)


@pytest.mark.parametrize("make", REFUSED)
def test_every_refusal_of_the_domain_can_be_worded(make: Callable[[], object]) -> None:
    """Values made directly (not through a parameter) are worded too: no ``KeyError``."""
    with pytest.raises(InvalidValueError) as caught:
        make()

    assert arguments.ParameterCheck.explained(caught.value).endswith(f"{caught.value.given!r}.")
