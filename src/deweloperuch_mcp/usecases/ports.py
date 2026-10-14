"""Ports (D13): how the domain and the use cases see the outside world.

Plain ``typing.Protocol`` classes that speak domain types only. The adapters of
deweloperuch.pl implement them (``deweloperuch_mcp.api``) and
``deweloperuch_mcp.bootstrap`` wires them into the use cases; tests may pass fakes.

Every port raises the domain's errors (``models.errors``): ``NotFoundError`` when the
service does not know what was asked for, ``UnexpectedResponseError`` when its answer
does not match the contract, and the errors of the transport (STOP, limiter, service,
closed session) as they are. The use cases say what each of them is about.
"""

import datetime as dt
from collections.abc import Callable, Mapping
from typing import Protocol, TypeVar

from deweloperuch_mcp.models.building import (
    Building,
    BuildingRef,
    BuildingSlug,
    NeighbourhoodTrend,
)
from deweloperuch_mcp.models.developer_match import DeveloperMatches, DeveloperName, MatchCount
from deweloperuch_mcp.models.developer_profile import DeveloperProfile
from deweloperuch_mcp.models.government_statistics import Dataset, LocationStatistics
from deweloperuch_mcp.models.investment import Investment
from deweloperuch_mcp.models.investment_summary import (
    InvestmentMatches,
    InvestmentName,
    InvestmentSummary,
)
from deweloperuch_mcp.models.investment_summary import InvestmentsLimit as SearchLimit
from deweloperuch_mcp.models.location import LocationMatches
from deweloperuch_mcp.models.location_ranking import LocationTransactions, RankingLevel
from deweloperuch_mcp.models.market_statistics import CityOffers
from deweloperuch_mcp.models.offer import InvestmentRef, OfferSearchCriteria, OfferSearchPage
from deweloperuch_mcp.models.price_history import PriceEvent
from deweloperuch_mcp.models.transaction_series import (
    Granularity,
    TransactionCity,
    TransactionSeries,
)
from deweloperuch_mcp.models.valuation import Valuation, ValuationSubject
from deweloperuch_mcp.models.values import (
    CitySlug,
    DeveloperSlug,
    InvestmentSlug,
    LocationQuery,
    LocationSlug,
    OfferId,
)


class LocationDirectory(Protocol):
    """Cities, districts and streets by a part of their name."""

    def cities(self, query: LocationQuery) -> LocationMatches:
        """Cities whose name contains ``query``, with their offer counts."""
        ...

    def districts_and_streets(self, query: LocationQuery) -> LocationMatches:
        """Districts and streets whose name contains ``query``, with coordinates."""
        ...


class OfferCatalog(Protocol):
    """The offers of developers' price lists."""

    def search(self, criteria: OfferSearchCriteria) -> OfferSearchPage:
        """One page of the offers matching ``criteria``; ``NotFoundError`` when the
        service does not know the city."""
        ...

    def price_events(self, offer_id: OfferId) -> tuple[PriceEvent, ...]:
        """Every price event of one offer, oldest first."""
        ...


class InvestmentCatalog(Protocol):
    """Investments with their offers."""

    def investment(self, slug: InvestmentSlug) -> Investment:
        """The investment with every offer (without their events)."""
        ...

    def price_events_of_offers(
        self, investment: Investment
    ) -> Mapping[int, tuple[PriceEvent, ...]]:
        """Offer id -> its price events, oldest first, for the offers that have any."""
        ...


class CityOffersSource(Protocol):
    """Every active offer of a city, compact, for the market summary (D15)."""

    def city_offers(self, city: CitySlug) -> CityOffers:
        """The offers of one city (never the whole country); ``NotFoundError`` when the
        service does not know the city."""
        ...


class DeveloperDirectory(Protocol):
    """Developers' profiles."""

    def developer(self, slug: DeveloperSlug, city: CitySlug) -> DeveloperProfile:
        """The profile in ``city`` (or the whole country); ``NotFoundError`` when the
        service does not know the developer (or the city)."""
        ...


class Clock(Protocol):
    """Today's date, for what depends on it (the windows of price flags)."""

    def today(self) -> dt.date: ...


class GovernmentStatisticsSource(Protocol):
    """The government statistics (GUS, NBP) a location has on the service."""

    def location_statistics(self, location: LocationSlug, dataset: Dataset) -> LocationStatistics:
        """Every dataset the service publishes for ``location``.

        Raises ``NotFoundError`` when the service does not know the location and
        ``UnexpectedResponseError`` when it does not answer as agreed, also when it shows
        ``dataset`` for the location but its data cannot be read (the other datasets do
        not matter for that).
        """
        ...


class PageLinks(Protocol):
    """Addresses of the service's public pages, for people (D12): ``None`` when one of
    the identities they need is missing. Never an address of data (no ``/api/``)."""

    def offers_list(self, criteria: OfferSearchCriteria) -> str | None:
        """The list of offers with the same criteria, order and page."""
        ...

    def investment(self, investment: InvestmentRef) -> str | None:
        """The investment's page."""
        ...

    def developer(self, investment: InvestmentRef) -> str | None:
        """The profile of the investment's developer."""
        ...

    def developer_in(self, city: str | None, developer_slug: str | None) -> str | None:
        """A developer's profile in ``city`` (a city slug or ``polska``)."""
        ...

    def government_statistics(self, location: LocationSlug, section: str | None) -> str | None:
        """The statistics of ``location``, at ``section`` when it is one."""
        ...


Status = TypeVar("Status", covariant=True)


class StopControl(Protocol[Status]):
    """The STOP every process of the package and ``recon/`` keeps to (D2): its record in
    the shared limiter. Local and offline; ``Status`` is the record's state as the
    limiter reports it (the use cases only pass it on)."""

    def status(self) -> Status:
        """The state at once, without waiting for the limiter's lock."""
        ...

    def clear(
        self, *, wait_limit: float, notice_after: float, on_wait: Callable[[], None] | None
    ) -> Status:
        """Remove the record; returns what it held. For people only."""
        ...


class DeveloperSearch(Protocol):
    """Developers by a part of their name."""

    def developers(self, name: DeveloperName, count: MatchCount) -> DeveloperMatches:
        """At most ``count`` developers whose name matches ``name``, in the service's
        order, with how many match in all and whether there are more."""
        ...


class DeveloperLinks(Protocol):
    """The profile page of a developer, for people (D12): ``None`` when the slug cannot
    make an address. Never an address of data."""

    def developer_profile(self, developer_slug: str, city: CitySlug) -> str | None:
        """The developer's profile in ``city`` (``polska``: the whole country)."""
        ...


class InvestmentDirectory(Protocol):
    """Investments as the service lists them for a search."""

    def in_city(self, city: CitySlug) -> tuple[InvestmentSummary, ...]:
        """Every investment of ``city`` the service lists, with its developer, offer
        counts and averages, in the service's order."""
        ...

    def by_name(self, name: InvestmentName, limit: SearchLimit) -> InvestmentMatches:
        """Investments whose name contains ``name``, across the country, in the service's
        order: at most ``limit`` of them (fewer if the service gives fewer), with how many
        match in all."""
        ...


class TransactionStatisticsSource(Protocol):
    """Prices of the RCN transactions of flats in a city over time."""

    def transaction_series(
        self, city: TransactionCity, granularity: Granularity
    ) -> TransactionSeries:
        """Every period the service has for ``city``, oldest first (none when it has no
        data for it).

        Raises ``NotFoundError`` when the service does not know the city and
        ``UnexpectedResponseError`` when its answer does not match the contract.
        """
        ...


class TransactionStatisticsLinks(Protocol):
    """The address of the service's public page of a city's transaction statistics, for
    people (D12); ``None`` when it cannot be built. Never an address of data."""

    def transaction_statistics(self, city: TransactionCity) -> str | None:
        """The page of the transaction prices of flats in ``city``."""
        ...


class TransactionRankingSource(Protocol):
    """The transactions of every city or powiat, as the service sums them up."""

    def locations(self, level: RankingLevel) -> tuple[LocationTransactions, ...]:
        """Every place of ``level`` the service ranks, in any order."""
        ...


class RankingLinks(Protocol):
    """The service's page of a ranking, for people (D12): ``None`` when there is none.
    Never an address of data (no ``/api/``)."""

    def city_ranking(self) -> str | None:
        """The service's ranking of cities."""
        ...


class BuildingCatalog(Protocol):
    """Buildings of the price register with their units and transactions."""

    def building(self, slug: BuildingSlug) -> Building:
        """The building with every unit and its transactions; ``NotFoundError`` when the
        service does not know ``slug``."""
        ...

    def neighbourhood_trend(self, building: Building) -> NeighbourhoodTrend:
        """The price per m² of the transactions around ``building``, every quarter."""
        ...


class BuildingPageLinks(Protocol):
    """The page of a building, for people (D12): ``None`` when an identity it needs is
    missing. Never an address of data (no ``/api/``)."""

    def building(self, building: BuildingRef) -> str | None:
        """The building's page with its transactions."""
        ...


class ValuationSource(Protocol):
    """Valuations of flats from the transactions (RCN) around them."""

    def valuation(self, subject: ValuationSubject) -> Valuation:
        """The service's estimate for ``subject`` with its comparable transactions; a
        valuation without an estimate (``estimated_value`` ``None``) when the service
        gives none."""
        ...
