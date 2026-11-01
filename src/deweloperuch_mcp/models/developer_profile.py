"""A developer's profile: its investments and cities, in one city or the whole country.

The port ``usecases.ports.DeveloperDirectory`` gives the profile as the service shows it
(``DeveloperProfile``): the investments with active offers in the profile's scope and
every city of the developer. ``DeveloperSummary.of`` sums investments up (the service
sends no totals since 2026-10-29), for the profile's summary and for the cities of
investments (``DeveloperCity.of_investments``); ``DeveloperProfile.listing`` is the rule of
what a result shows: the investments with the most active offers first, at most
``limit`` of them, with the number left out (D4), and every city, the most active offers
first. Single offers are not part of a profile.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from deweloperuch_mcp.models.offer import DeveloperRef, InvestmentRef
from deweloperuch_mcp.models.values import CitySlug, InvestmentsLimit

DEFAULT_INVESTMENTS_LIMIT = 20
"""Investments a result shows unless asked otherwise."""


@dataclass(frozen=True, kw_only=True)
class DeveloperInvestment:
    """An investment on a developer's profile, with the service's own figures."""

    investment_slug: str
    name: str
    city: str | None
    city_slug: str | None
    status: str
    active_offers: int | None
    total_offers: int | None
    """Active and archived offers."""
    avg_price: float | None
    """Mean price of the active offers."""
    avg_area_m2: float | None
    """Mean area of the active offers."""
    avg_price_per_m2: float | None
    """Price per m² of the active offers, as the service counts it (their total price over
    their total area)."""
    developer: DeveloperRef

    @property
    def ref(self) -> InvestmentRef:
        return InvestmentRef(
            investment_slug=self.investment_slug,
            name=self.name,
            city=self.city,
            city_slug=self.city_slug,
            developer=self.developer,
        )


@dataclass(frozen=True, kw_only=True)
class DeveloperCity:
    """A city where a developer has active offers, with the service's own figures."""

    city: str
    city_slug: str
    investments: int | None
    active_offers: int | None
    avg_price_per_m2: float | None
    """The price per m² of the city's investments weighted by their active offers, as the
    service counts it, to the nearest PLN. ``DeveloperSummary.of`` those investments
    counts the same way from their figures rounded to whole PLN, so the two may differ by
    1 PLN."""

    @classmethod
    def of_investments(
        cls, investments: Sequence[DeveloperInvestment]
    ) -> tuple["DeveloperCity", ...]:
        """The cities of ``investments``, each summed up as ``DeveloperSummary.of`` sums up a
        profile, in the order of their first investment. A city without a name is named by
        its slug; investments without a city are left out."""
        by_city: dict[str, list[DeveloperInvestment]] = {}
        for item in investments:
            if item.city_slug:
                by_city.setdefault(item.city_slug, []).append(item)
        return tuple(cls._of(city_slug, mine) for city_slug, mine in by_city.items())

    @classmethod
    def _of(cls, city_slug: str, investments: Sequence[DeveloperInvestment]) -> "DeveloperCity":
        summary = DeveloperSummary.of(investments)
        return cls(
            city=next((item.city for item in investments if item.city), city_slug),
            city_slug=city_slug,
            investments=summary.investments,
            active_offers=summary.active_offers,
            avg_price_per_m2=summary.avg_price_per_m2,
        )


@dataclass(frozen=True, kw_only=True)
class DeveloperSummary:
    """The developer's active offers in the profile's city (or the whole country)."""

    investments: int
    active_offers: int | None
    """``None`` when an investment's count is unknown."""
    cities: int
    avg_price: float | None
    """Mean price of the active offers, to the nearest PLN."""
    avg_area_m2: float | None
    """Mean area of the active offers, to 0.01 m²."""
    avg_price_per_m2: float | None
    """The investments' price per m² weighted by their active offers, to the nearest PLN
    (``DeveloperCity.avg_price_per_m2`` of one city may differ by 1 PLN)."""

    @classmethod
    def of(cls, investments: Sequence[DeveloperInvestment]) -> "DeveloperSummary":
        """``investments`` summed up: how many, their active offers and cities, and the
        averages of their active offers (each investment's average weighted by its active
        offers, which gives the mean of every active offer for a mean price or area).

        An unknown count of active offers makes the totals and averages unknown; an
        average that an investment with active offers lacks is unknown too.
        """
        counts = [item.active_offers for item in investments]
        return cls(
            investments=len(counts),
            active_offers=None if None in counts else sum(count or 0 for count in counts),
            cities=len({item.city_slug for item in investments if item.city_slug}),
            avg_price=cls._weighted(investments, lambda item: item.avg_price, 0),
            avg_area_m2=cls._weighted(investments, lambda item: item.avg_area_m2, 2),
            avg_price_per_m2=cls._weighted(investments, lambda item: item.avg_price_per_m2, 0),
        )

    @staticmethod
    def _weighted(
        investments: Sequence[DeveloperInvestment],
        figure: Callable[[DeveloperInvestment], float | None],
        digits: int,
    ) -> float | None:
        """``figure`` of the investments with active offers, weighted by them and rounded
        to ``digits``; ``None`` when an investment's count is unknown, one with active
        offers lacks the figure, or none has active offers."""
        offers, total = 0, 0.0
        for item in investments:
            count = item.active_offers
            if count is None:
                return None
            if count <= 0:
                continue
            value = figure(item)
            if value is None:
                return None
            offers += count
            total += value * count
        return round(total / offers, digits) if offers else None


@dataclass(frozen=True, kw_only=True)
class DeveloperProfile:
    """A developer in a city (or the whole country, ``polska``)."""

    developer: DeveloperRef
    city: CitySlug
    """The scope of ``investments`` and ``summary``."""
    investments: tuple[DeveloperInvestment, ...]
    """In the service's order."""
    cities: tuple[DeveloperCity, ...]
    """Every city of the developer, whatever the scope, in the service's order; the cities
    of ``investments`` when the service sent no list of them (``cities_from_investments``)."""
    cities_from_investments: bool = False
    """The service sent no list of the developer's cities: ``cities`` are those of
    ``investments`` (``DeveloperCity.of_investments``)."""

    @property
    def cities_in_scope_only(self) -> bool:
        """``cities`` may lack the developer's other cities: they come from the investments
        and the scope is one city. The investments of the whole country are in every city
        of the developer."""
        return self.cities_from_investments and not self.city.whole_country

    @property
    def summary(self) -> DeveloperSummary:
        """The investments summed up (``DeveloperSummary.of``)."""
        return DeveloperSummary.of(self.investments)

    def listing(self, limit: InvestmentsLimit) -> "DeveloperListing":
        """The investments with the most active offers first (unknown counts last, ties
        in the service's order), at most ``limit``; every city, the most active offers
        first, then the higher price per m² (unknown figures last, ties in the service's
        order), whatever order the service sent."""
        ordered = sorted(  # stable: ties keep the service's order
            self.investments,
            key=lambda item: (item.active_offers is None, -(item.active_offers or 0)),
        )
        kept = tuple(ordered[: limit.value])
        cities = sorted(  # stable as well
            self.cities,
            key=lambda city: (
                city.active_offers is None,
                -(city.active_offers or 0),
                city.avg_price_per_m2 is None,
                -(city.avg_price_per_m2 or 0.0),
            ),
        )
        return DeveloperListing(
            profile=self,
            investments=kept,
            omitted=len(ordered) - len(kept),
            cities=tuple(cities),
        )


@dataclass(frozen=True, kw_only=True)
class DeveloperListing:
    """What a result shows of a profile: the investments kept, how many were left out, and
    every city in the order a result shows them."""

    profile: DeveloperProfile
    investments: tuple[DeveloperInvestment, ...]
    omitted: int
    cities: tuple[DeveloperCity, ...]
