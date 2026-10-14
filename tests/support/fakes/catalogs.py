"""In-memory stand-ins of the read ports of the use cases (``usecases.ports``), with the
canned answers they give: ``FakeCatalogs`` is every catalog at once and records the
calls; ``EchoPageLinks`` says which page it was asked for.
"""

import datetime as dt
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from deweloperuch_mcp.models.developer_profile import (
    DeveloperInvestment,
    DeveloperProfile,
    DeveloperSummary,
)
from deweloperuch_mcp.models.government_statistics import (
    Dataset,
    Frequency,
    LocationStatistics,
    SeriesPoint,
    StatisticsTable,
    TimeSeries,
    Unit,
)
from deweloperuch_mcp.models.investment import Investment
from deweloperuch_mcp.models.location import Location, LocationMatches
from deweloperuch_mcp.models.market_statistics import CityOffers, MarketOffer
from deweloperuch_mcp.models.offer import (
    DeveloperRef,
    InvestmentRef,
    Offer,
    OfferSearchCriteria,
    OfferSearchPage,
)
from deweloperuch_mcp.models.price_history import PriceEvent
from deweloperuch_mcp.models.values import (
    CitySlug,
    DeveloperSlug,
    InvestmentSlug,
    LocationQuery,
    LocationSlug,
    OfferId,
)
from deweloperuch_mcp.usecases import ports

DEVELOPER = DeveloperRef(developer_slug="atal", name="ATAL S.A.")


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
class FakeCatalogs:
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

    # CityOffersSource
    def city_offers(self, city: CitySlug) -> CityOffers:
        self._call(f"city_offers {city.value}")
        return CityOffers(city=city, offers=self.market)

    market: tuple[MarketOffer, ...] = ()

    # DeveloperDirectory
    def developer(self, slug: DeveloperSlug, city: CitySlug) -> DeveloperProfile:
        self._call(f"developer {slug.value} {city.value}")
        return DeveloperProfile(
            developer=DEVELOPER,
            city=city,
            summary=DeveloperSummary(
                investments=len(self.projects),
                active_offers=None,
                cities=None,
                avg_price=None,
                avg_area_m2=None,
                avg_price_per_m2=None,
            ),
            investments=self.projects,
            cities=(),
        )

    projects: tuple[DeveloperInvestment, ...] = ()


@dataclass
class EchoPageLinks:
    """``PageLinks`` that says what it was asked for."""

    def offers_list(self, criteria: OfferSearchCriteria) -> str | None:
        return f"list:{criteria.city.value}:{criteria.page.value}"

    def investment(self, investment: InvestmentRef) -> str | None:
        return f"investment:{investment.investment_slug}"

    def developer(self, investment: InvestmentRef) -> str | None:
        return f"developer:{investment.developer.developer_slug}"

    def developer_in(self, city: str | None, developer_slug: str | None) -> str | None:
        return f"developer:{city}:{developer_slug}"

    def government_statistics(self, location: LocationSlug, section: str | None) -> str | None:
        return f"stats:{location.value}#{section}"


def published(location: str) -> LocationStatistics:
    series = TimeSeries("rate", "Stopa", Unit.PERCENT, (SeriesPoint("2025", 5.0),))
    table = StatisticsTable(Dataset.UNEMPLOYMENT, Frequency.YEAR, "GUS", (series,), "gus-x")
    return LocationStatistics(LocationSlug(location), location.title(), {table.dataset: table})


if TYPE_CHECKING:  # mypy checks that each fake is the port it stands in for
    _location_directory: ports.LocationDirectory = FakeCatalogs()
    _offer_catalog: ports.OfferCatalog = FakeCatalogs()
    _investment_catalog: ports.InvestmentCatalog = FakeCatalogs()
    _city_offers_source: ports.CityOffersSource = FakeCatalogs()
    _developer_directory: ports.DeveloperDirectory = FakeCatalogs()
    _government_statistics_source: ports.GovernmentStatisticsSource = FakeCatalogs()
    _page_links: ports.PageLinks = EchoPageLinks()
