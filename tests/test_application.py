"""The use cases (D13) over fake ports: what they ask the ports, in which order, how they
word a port's failure for the caller (D12) and which links they attach. No HTTP at all:
the adapters of the service are tested in tests/test_services.py, test_client_*.py and
the goldens.
"""

import datetime as dt
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

import pytest

from deweloperuch_mcp.application import arguments
from deweloperuch_mcp.application.investments import GetInvestment
from deweloperuch_mcp.application.locations import SearchLocations
from deweloperuch_mcp.application.offers import GetOffer, SearchOffers, offers_hint
from deweloperuch_mcp.application.statistics import GetGovernmentStatistics, statistics_hint
from deweloperuch_mcp.application.stop import ClearStop, StopStatus
from deweloperuch_mcp.domain import ports
from deweloperuch_mcp.domain.errors import (
    InvalidInputError,
    NotFoundError,
    ServiceBlockedError,
    ServiceError,
    UnexpectedResponseError,
)
from deweloperuch_mcp.domain.investments import Investment
from deweloperuch_mcp.domain.locations import Location, LocationMatches
from deweloperuch_mcp.domain.offers import (
    Developer,
    InvestmentRef,
    ListedOffer,
    Offer,
    OfferSearchCriteria,
    OfferSearchPage,
    PriceEvent,
)
from deweloperuch_mcp.domain.statistics import (
    Dataset,
    Frequency,
    LocationStatistics,
    PeriodCount,
    SeriesPoint,
    StatisticsTable,
    TimeSeries,
    Unit,
)
from deweloperuch_mcp.domain.values import (
    InvestmentSlug,
    LocationQuery,
    LocationSlug,
    OfferId,
    OffersLimit,
)

DEVELOPER = Developer(developer_slug="atal", name="ATAL S.A.")
EVENTS = (
    PriceEvent(date=dt.date(2025, 2, 25), kind="offer", price=1.0),
    PriceEvent(date=dt.date(2026, 10, 3), kind="restored", price=2.0),
)


def offer(offer_id: int, status: str = "active") -> Offer:
    return Offer(offer_id=offer_id, name=f"M{offer_id}", status=status, price=1.0, area_m2=1.0)


INVESTMENT = Investment(
    investment_id=33,
    investment_slug="smolna",
    name="Smolna",
    status="active",
    city="Sopot",
    city_slug="sopot",
    developer=DEVELOPER,
    offers=(offer(1, "archived"), offer(2), offer(3)),
)


@dataclass
class Fake:
    """Every port at once: records the calls, answers or raises what a test sets."""

    calls: list[str] = field(default_factory=list)
    errors: dict[str, Exception] = field(default_factory=dict)
    page: OfferSearchPage = field(
        default_factory=lambda: OfferSearchPage(items=(), total=0, page=1, per_page=10)
    )
    published: LocationStatistics | None = None

    def _call(self, name: str) -> None:
        self.calls.append(name)
        if name in self.errors:
            raise self.errors[name]

    # LocationDirectory
    def cities(self, query: LocationQuery) -> LocationMatches:
        self._call("cities")
        return LocationMatches(
            (Location.city_of(name="Kraków", city_slug="krakow", offer_count=1),)
        )

    def districts_and_streets(self, query: LocationQuery) -> LocationMatches:
        self._call("districts_and_streets")
        return LocationMatches((), more=True)

    # OfferCatalog
    def search(self, criteria: OfferSearchCriteria) -> OfferSearchPage:
        self._call("search")
        return self.page

    def price_events(self, offer_id: OfferId) -> tuple[PriceEvent, ...]:
        self._call(f"price_events {offer_id.value}")
        return EVENTS

    # InvestmentCatalog
    def investment(self, slug: InvestmentSlug) -> Investment:
        self._call(f"investment {slug.value}")
        return INVESTMENT

    def price_events_of_offers(
        self, investment: Investment
    ) -> Mapping[int, tuple[PriceEvent, ...]]:
        self._call(f"price_events_of_offers {investment.investment_id}")
        return {2: EVENTS}

    # GovernmentStatisticsSource
    def location_statistics(self, location: LocationSlug, dataset: Dataset) -> LocationStatistics:
        self._call(f"location_statistics {location.value} {dataset.value}")
        assert self.published is not None
        return self.published


@dataclass
class Links:
    """``PageLinks`` that says what it was asked for."""

    def offers_list(self, criteria: OfferSearchCriteria) -> str | None:
        return f"list:{criteria.city.value}:{criteria.page.value}"

    def investment(self, investment: InvestmentRef) -> str | None:
        return f"investment:{investment.investment_slug}"

    def developer(self, investment: InvestmentRef) -> str | None:
        return f"developer:{investment.developer.developer_slug}"

    def government_statistics(self, location: LocationSlug, section: str | None) -> str | None:
        return f"stats:{location.value}#{section}"


def test_the_fakes_are_the_ports() -> None:
    """The fakes satisfy the protocols, so the use cases are tested against the ports."""
    fake = Fake()
    directory: ports.LocationDirectory = fake
    catalog: ports.OfferCatalog = fake
    investments: ports.InvestmentCatalog = fake
    source: ports.GovernmentStatisticsSource = fake
    links: ports.PageLinks = Links()
    control: ports.StopControl[str] = Control()

    assert all(port is fake for port in (directory, catalog, investments, source))
    assert isinstance(links, Links) and isinstance(control, Control)


# --- search locations -----------------------------------------------------------------------------


def test_locations_ask_cities_then_districts_and_streets() -> None:
    fake = Fake()

    result = SearchLocations(fake)(LocationQuery("krak"))

    assert fake.calls == ["cities", "districts_and_streets"]
    assert [item.name for item in result.items] == ["Kraków"]
    assert (result.total, result.truncated) == (None, True)


@pytest.mark.parametrize(
    ("failing", "subject"),
    [("cities", "Wyszukiwanie miast"), ("districts_and_streets", "Wyszukiwanie dzielnic i ulic")],
)
def test_a_location_source_failure_names_the_search(failing: str, subject: str) -> None:
    fake = Fake(errors={failing: ServiceError("Serwis odpowiedział błędem HTTP 500.", 3.0)})

    with pytest.raises(ServiceError) as caught:
        SearchLocations(fake)(LocationQuery("krak"))

    assert type(caught.value) is ServiceError
    assert str(caught.value) == f"{subject}: Serwis odpowiedział błędem HTTP 500."
    assert caught.value.pause_seconds == 3.0


# --- search offers --------------------------------------------------------------------------------


def listed(offer_id: int) -> ListedOffer:
    ref = InvestmentRef(
        investment_slug=f"inv-{offer_id}", name="I", city=None, city_slug=None, developer=DEVELOPER
    )
    return ListedOffer(offer=offer(offer_id), investment=ref)


def test_a_search_gets_its_links() -> None:
    page = OfferSearchPage(items=(listed(1), listed(2)), total=2, page=1, per_page=10)
    fake = Fake(page=page)

    found = SearchOffers(fake, Links())(arguments.offer_search("krakow", page=3))

    assert fake.calls == ["search"]
    assert found.page is page
    assert found.list_url == "list:krakow:3"
    assert found.investment_urls == ("investment:inv-1", "investment:inv-2")


def search_page(total: int, page: int = 1, per_page: int = 10, items: int = 3) -> OfferSearchPage:
    listed_offers = tuple(listed(index) for index in range(items))
    return OfferSearchPage(items=listed_offers, total=total, page=page, per_page=per_page)


@pytest.mark.parametrize(
    ("page", "hint"),
    [
        (
            search_page(13324),
            "Pasujących ofert jest 13324, a serwis pozwala przejrzeć najwyżej 20 stron po 10 "
            "(200). Zawęź filtry (cena, metraż) albo zwiększ per_page do 100.",
        ),
        (
            search_page(13324, per_page=100),
            "Pasujących ofert jest 13324, a serwis pozwala przejrzeć najwyżej 20 stron po 100 "
            "(2000). Zawęź filtry (cena, metraż).",
        ),
        (
            search_page(0, items=0),
            "Brak ofert spełniających kryteria. Sprawdź slug miasta (search_locations) i "
            "poluzuj filtry.",
        ),
        (search_page(30, page=9, items=0), "Strona 9 jest pusta; dostępne strony: 1–3."),
        (search_page(2000, per_page=100), None),
        (search_page(3), None),
    ],
)
def test_a_search_says_what_to_do_next(page: OfferSearchPage, hint: str | None) -> None:
    """The domain knows the cut (D4); the use case says it with the operations' names."""
    assert offers_hint(page) == hint
    assert SearchOffers(Fake(page=page), Links())(arguments.offer_search("x")).hint == hint


def test_an_unknown_city_points_to_search_locations() -> None:
    fake = Fake(errors={"search": NotFoundError("Serwis nie zna żądanych danych.", detail="d")})

    with pytest.raises(NotFoundError) as caught:
        SearchOffers(fake, Links())(arguments.offer_search("atlantyda"))

    assert str(caught.value) == (
        "Serwis nie zna miasta 'atlantyda'. Podaj city_slug z search_locations albo polska "
        "(cały kraj)."
    )
    assert caught.value.detail == "d"


def test_unexpected_data_keeps_its_type_and_names_the_search() -> None:
    fake = Fake(errors={"search": UnexpectedResponseError("Inny format.", detail="x")})

    with pytest.raises(UnexpectedResponseError, match="^Wyszukiwanie ofert w 'warszawa': Inny"):
        SearchOffers(fake, Links())(arguments.offer_search("warszawa"))


@pytest.mark.parametrize(
    "error", [ServiceBlockedError("STOP: 403."), InvalidInputError("Błąd programu.")]
)
def test_stop_and_input_errors_pass_unchanged(error: Exception) -> None:
    fake = Fake(errors={"search": error})

    with pytest.raises(type(error)) as caught:
        SearchOffers(fake, Links())(arguments.offer_search("warszawa"))

    assert caught.value is error


# --- an offer -------------------------------------------------------------------------------------


def test_an_offer_comes_with_its_history_and_links() -> None:
    fake = Fake()

    found = GetOffer(fake, fake, Links())(OfferId(2), InvestmentSlug("smolna"))

    assert fake.calls == ["investment smolna", "price_events 2"]
    assert found.detail.offer.offer_id == 2
    assert found.detail.offer.history.events == EVENTS
    assert found.detail.investment is INVESTMENT
    assert (found.investment_url, found.developer_url) == ("investment:smolna", "developer:atal")


def test_an_offer_outside_its_investment_is_not_found_without_asking_for_events() -> None:
    fake = Fake()

    with pytest.raises(NotFoundError) as caught:
        GetOffer(fake, fake, Links())(OfferId(999), InvestmentSlug("smolna"))

    assert str(caught.value) == (
        "Inwestycja 'smolna' nie ma oferty 999. Sprawdź offer_id i investment_slug (oba podaje "
        "search_offers); wszystkie oferty inwestycji zwraca get_investment."
    )
    assert fake.calls == ["investment smolna"]


def test_an_unknown_investment_says_where_slugs_come_from() -> None:
    fake = Fake(errors={"investment smolna": NotFoundError("404")})

    with pytest.raises(NotFoundError) as caught:
        GetOffer(fake, fake, Links())(OfferId(2), InvestmentSlug("smolna"))

    assert str(caught.value) == (
        "Nie znaleziono inwestycji 'smolna'. Slug inwestycji podaje search_offers (pole "
        "investment_slug)."
    )


def test_an_offer_without_history_is_explained() -> None:
    fake = Fake(errors={"price_events 2": NotFoundError("404")})

    with pytest.raises(NotFoundError, match="^Serwis nie ma historii ceny oferty 2 z inwestycji"):
        GetOffer(fake, fake, Links())(OfferId(2), InvestmentSlug("smolna"))


# --- an investment --------------------------------------------------------------------------------


def test_an_investment_without_history_asks_once() -> None:
    fake = Fake()

    found = GetInvestment(fake, Links())(InvestmentSlug("smolna"), limit=OffersLimit(2))

    assert fake.calls == ["investment smolna"]
    assert [o.offer_id for o in found.listing.offers] == [2, 3]  # active first
    assert found.listing.omitted == 1
    assert all(o.history.events is None for o in found.listing.offers)
    assert (found.investment_url, found.developer_url) == ("investment:smolna", "developer:atal")


def test_an_investment_with_history_attaches_it_to_the_offers_kept() -> None:
    fake = Fake()

    found = GetInvestment(fake, Links())(InvestmentSlug("smolna"), include_history=True)

    assert fake.calls == ["investment smolna", "price_events_of_offers 33"]
    assert [o.history.events for o in found.listing.offers] == [EVENTS, (), ()]


def test_an_investment_without_histories_is_explained() -> None:
    fake = Fake(errors={"price_events_of_offers 33": NotFoundError("404")})

    with pytest.raises(NotFoundError, match="get_offer"):
        GetInvestment(fake, Links())(InvestmentSlug("smolna"), include_history=True)


# --- government statistics ------------------------------------------------------------------------


def published(location: str) -> LocationStatistics:
    series = TimeSeries("rate", "Stopa", Unit.PERCENT, (SeriesPoint("2025", 5.0),))
    table = StatisticsTable(Dataset.UNEMPLOYMENT, Frequency.YEAR, "GUS", (series,), "gus-x")
    return LocationStatistics(LocationSlug(location), location.title(), {table.dataset: table})


def test_statistics_come_with_the_link_to_their_section() -> None:
    fake = Fake(published=published("warszawa"))

    found = GetGovernmentStatistics(fake, Links())(
        LocationSlug("warszawa"), Dataset.UNEMPLOYMENT, PeriodCount(1)
    )

    assert fake.calls == ["location_statistics warszawa unemployment"]
    assert found.statistics.returned == 1
    assert found.stats_url == "stats:warszawa#gus-x"


def test_truncated_statistics_say_how_to_see_older_periods() -> None:
    series = TimeSeries(
        "rate", "Stopa", Unit.PERCENT, tuple(SeriesPoint(str(y), 1.0) for y in range(2001, 2026))
    )
    table = StatisticsTable(Dataset.UNEMPLOYMENT, Frequency.YEAR, "GUS", (series,), None)
    published = LocationStatistics(LocationSlug("x"), "X", {table.dataset: table})

    cut = published.statistics(Dataset.UNEMPLOYMENT, PeriodCount(3))
    whole = published.statistics(Dataset.UNEMPLOYMENT, PeriodCount(25))

    assert statistics_hint(cut) == (
        "Pokazano ostatnie 3 z 25 okresów (dane od 2001); starsze pokaże większa wartość periods."
    )
    assert statistics_hint(whole) is None


def test_a_dataset_not_published_is_the_domains_message_unwrapped() -> None:
    fake = Fake(published=published("warszawa"))

    with pytest.raises(NotFoundError) as caught:
        GetGovernmentStatistics(fake, Links())(
            LocationSlug("warszawa"), Dataset.WAGES, PeriodCount()
        )

    assert str(caught.value).startswith("Serwis nie publikuje zestawu 'wages'")


def test_an_unknown_location_says_what_to_give() -> None:
    fake = Fake(errors={"location_statistics x unemployment": NotFoundError("404")})

    with pytest.raises(
        NotFoundError, match="^Serwis nie ma statystyk rządowych dla lokalizacji 'x'"
    ):
        GetGovernmentStatistics(fake, Links())(
            LocationSlug("x"), Dataset.UNEMPLOYMENT, PeriodCount()
        )


# --- the STOP record ------------------------------------------------------------------------------


@dataclass
class Control:
    cleared: list[tuple[float, float, Callable[[], None] | None]] = field(default_factory=list)

    def status(self) -> str:
        return "state"

    def clear(
        self, *, wait_limit: float, notice_after: float, on_wait: Callable[[], None] | None
    ) -> str:
        self.cleared.append((wait_limit, notice_after, on_wait))
        return "before"


def test_stop_use_cases_pass_the_state_on() -> None:
    control = Control()

    assert StopStatus(control)() == "state"
    assert ClearStop(control)(wait_limit=1.0, notice_after=0.5) == "before"
    assert control.cleared == [(1.0, 0.5, None)]
