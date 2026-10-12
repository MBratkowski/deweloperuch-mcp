"""Ports (D13): how the domain and the use cases see the outside world.

Plain ``typing.Protocol`` classes that speak domain types only. The adapters of
deweloperuch.pl implement them (``deweloperuch_mcp.infrastructure``) and
``deweloperuch_mcp.bootstrap`` wires them into the use cases; tests may pass fakes.

Every port raises the domain's errors (``domain.errors``): ``NotFoundError`` when the
service does not know what was asked for, ``UnexpectedResponseError`` when its answer
does not match the contract, and the errors of the transport (STOP, limiter, service,
closed session) as they are. The use cases say what each of them is about.
"""

from collections.abc import Callable, Mapping
from typing import Protocol, TypeVar

from deweloperuch_mcp.domain.investments import Investment
from deweloperuch_mcp.domain.locations import LocationMatches
from deweloperuch_mcp.domain.offers import (
    InvestmentRef,
    OfferSearchCriteria,
    OfferSearchPage,
    PriceEvent,
)
from deweloperuch_mcp.domain.statistics import Dataset, LocationStatistics
from deweloperuch_mcp.domain.values import InvestmentSlug, LocationQuery, LocationSlug, OfferId


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
