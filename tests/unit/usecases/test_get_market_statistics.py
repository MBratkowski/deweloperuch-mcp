"""Tests of ``deweloperuch_mcp.usecases.get_market_statistics``."""

import pytest

from deweloperuch_mcp.models.errors import InvalidInputError, NotFoundError, ServiceError
from deweloperuch_mcp.models.market_statistics import MarketCity, MarketOffer
from deweloperuch_mcp.usecases.get_market_statistics import (
    GetMarketStatistics,
    GetMarketStatisticsRequest,
)
from support.fakes.catalogs import EchoPageLinks, FakeCatalogs
from support.fakes.places import VILLAGE, FakePlaces, unknown_place_message


def market_offer(offer_id: int, developer: str, price: float, area: float) -> MarketOffer:
    return MarketOffer(
        offer_id=offer_id,
        investment_slug=f"inv-{developer}",
        developer_slug=developer,
        developer_name=developer.upper(),
        price=price,
        area_m2=area,
    )


def test_the_market_is_one_request_and_links_its_list_and_developers() -> None:
    fake = FakeCatalogs(
        market=(market_offer(1, "atal", 500_000, 50), market_offer(2, "dom", 900, 1))
    )
    request = GetMarketStatisticsRequest.parse(city="krakow", price_min=1_000, top_developers=1)

    places = FakePlaces()

    found = GetMarketStatistics(fake, EchoPageLinks(), places).execute(request)

    assert fake.calls == ["city_offers krakow"]
    assert places.calls == []
    assert (found.statistics.offers, found.hint) == (1, None)
    assert found.list_url == "list:krakow:1"
    assert found.developer_urls == ("developer:krakow:atal",)


def test_the_city_of_the_market_is_a_city_of_its_own() -> None:
    assert GetMarketStatisticsRequest.parse(city=" krakow ").criteria.city == MarketCity("krakow")


@pytest.mark.parametrize("city", ["Kraków", "KRAKOW", "krakow/mieszkania", ""])
def test_a_city_that_is_no_slug_is_refused_in_the_words_of_the_market(city: str) -> None:
    with pytest.raises(InvalidInputError) as caught:
        GetMarketStatisticsRequest.parse(city=city)

    assert str(caught.value) == (
        "city: oczekiwano slug jednego miasta z search_locations: małe litery, bez polskich "
        f"znaków (np. warszawa, sopot; nie polska); podano {city!r}."
    )


def test_an_empty_market_says_what_to_do() -> None:
    found = GetMarketStatistics(FakeCatalogs(), EchoPageLinks(), FakePlaces()).execute(
        GetMarketStatisticsRequest.parse(city="krakow")
    )

    assert found.statistics.offers == 0
    assert found.hint == (
        "Brak aktywnych ofert spełniających kryteria w 'krakow'. Sprawdź slug miasta "
        "(search_locations) i poluzuj filtry (cena, metraż)."
    )


def not_found(city: str, places: FakePlaces) -> NotFoundError:
    """What the market of ``city`` ends with when the service does not know it."""
    fake = FakeCatalogs(errors={f"city_offers {city}": NotFoundError("404", detail="/api/x")})
    with pytest.raises(NotFoundError) as caught:
        GetMarketStatistics(fake, EchoPageLinks(), places).execute(
            GetMarketStatisticsRequest.parse(city=city)
        )
    return caught.value


def test_an_unknown_place_says_there_is_no_such_place() -> None:
    places = FakePlaces()

    found = not_found("nieznane", places)

    assert str(found) == (
        unknown_place_message("nieznane")
        + " Statystyki rynku są tylko dla jednego miasta (nie dla polska ani agregatów)."
    )
    assert (found.detail, places.calls) == ("/api/x", ["nieznane"])


def test_a_known_place_without_offers_says_so() -> None:
    found = not_found(VILLAGE.slug, FakePlaces.knowing(VILLAGE))

    assert str(found) == (
        "Miejscowość 'Ignatki-osiedle' istnieje, ale serwis nie ma dla niej statystyk rynku. "
        "Nie ponawiaj; powiedz to użytkownikowi."
    )


def test_a_failed_lookup_keeps_the_markets_own_answer() -> None:
    """An unknown city, or one the service lists without offers [H]: the same answer."""
    found = not_found("nieznane", FakePlaces(failure=ServiceError("503")))

    assert str(found) == (
        "Serwis nie zna miasta 'nieznane' albo nie ma w nim ofert. Podaj city_slug z "
        "search_locations (miejscowości z offer_count=0 nie mają statystyk; statystyki rynku "
        "są tylko dla jednego miasta)."
    )
