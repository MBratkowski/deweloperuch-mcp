"""``MarketStatistics``: the offer market of a city in numbers (D15): counts, quartiles,
the largest developers.

The port ``usecases.ports.CityOffersSource`` gives every active offer of one city in a
compact form (``CityOffers``); ``CityOffers.statistics`` narrows them to the ranges of
price and area of ``MarketCriteria`` and sums them up. The source lists one city at a
time, never the whole country [P 2026-10-10], so the criteria refuse ``polska``
(``MarketCriteria.one_city``). Single offers never leave this module: a result holds
only aggregates and a bounded list of developers (D5, D15).

Quantiles are linear between the closest ranks (the "inclusive" method: ``p25`` of
1, 2, 3, 4 is 1.75), the median the middle value or the mean of the two middle ones.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass

from deweloperuch_mcp.models.errors import InvalidValueError, OneCity, ValueName
from deweloperuch_mcp.models.offer import ACTIVE
from deweloperuch_mcp.models.values import AreaRange, CitySlug, DeveloperCount, PriceRange

DEFAULT_TOP_DEVELOPERS = 10
"""Developers a summary names unless asked otherwise."""


@dataclass(frozen=True, kw_only=True)
class MarketCriteria:
    """What a market summary asks for: one city, optional ranges of price and area, and
    how many of the largest developers to name."""

    city: CitySlug
    price: PriceRange | None = None
    area: AreaRange | None = None
    top: DeveloperCount = DeveloperCount(DEFAULT_TOP_DEVELOPERS)

    def __post_init__(self) -> None:
        self.one_city(self.city)

    @staticmethod
    def one_city(city: CitySlug) -> CitySlug:
        """``city``, unless it is the whole country (the market is of one city)."""
        if city.whole_country:
            raise InvalidValueError(ValueName.CITY, OneCity(), city.value)
        return city


@dataclass(frozen=True, kw_only=True)
class MarketOffer:
    """An offer of a city's market: only what the summary counts."""

    offer_id: int
    investment_slug: str | None
    """``None`` when the offer names no investment the city lists."""
    developer_slug: str | None
    status: str
    price: float | None
    area_m2: float | None

    @property
    def price_per_m2(self) -> float | None:
        """``price / area_m2`` rounded to 0.01, as ``Offer.price_per_m2``."""
        if self.price is None or not self.area_m2:
            return None
        return round(self.price / self.area_m2, 2)


@dataclass(frozen=True, kw_only=True)
class Spread:
    """The smallest value, the quartiles, the median and the largest one."""

    min: float
    p25: float
    median: float
    p75: float
    max: float

    @classmethod
    def of(cls, values: Sequence[float]) -> "Spread | None":
        """``None`` for no values."""
        if not values:
            return None
        ordered = sorted(values)
        return cls(
            min=ordered[0],
            p25=cls.quantile(ordered, 0.25),
            median=cls.quantile(ordered, 0.5),
            p75=cls.quantile(ordered, 0.75),
            max=ordered[-1],
        )

    @staticmethod
    def quantile(ordered: Sequence[float], q: float) -> float:
        """The ``q`` quantile (0..1) of sorted values, linear between the closest ranks."""
        position = (len(ordered) - 1) * q
        low = math.floor(position)
        high = min(low + 1, len(ordered) - 1)
        return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


@dataclass(frozen=True, kw_only=True)
class DeveloperShare:
    """A developer's part of a city's market."""

    developer_slug: str
    offers: int
    investments: int
    median_price_per_m2: float | None


@dataclass(frozen=True, kw_only=True)
class MarketStatistics:
    """The offers of a city that match the criteria, summed up."""

    criteria: MarketCriteria
    offers: int
    investments: int
    developers: int
    """Developers with at least one matching offer."""
    price_spread: Spread | None
    price_per_m2_spread: Spread | None
    area_spread: Spread | None
    top_developers: tuple[DeveloperShare, ...]
    """The developers with the most matching offers, most first (ties by slug)."""

    @property
    def developers_omitted(self) -> int:
        return self.developers - len(self.top_developers)


@dataclass(frozen=True, kw_only=True)
class CityOffers:
    """Every active offer of a city, as the service lists them for its market."""

    city: CitySlug
    offers: tuple[MarketOffer, ...]

    def matching(self, price: PriceRange | None, area: AreaRange | None) -> list[MarketOffer]:
        """Active offers within both ranges (ends included); an offer without a price
        (an area) does not match a range of prices (areas)."""
        return [
            offer
            for offer in self.offers
            if offer.status == ACTIVE
            and _within(offer.price, price)
            and _within(offer.area_m2, area)
        ]

    def statistics(self, criteria: MarketCriteria) -> MarketStatistics:
        found = self.matching(criteria.price, criteria.area)
        by_developer: dict[str, list[MarketOffer]] = {}
        for offer in found:
            if offer.developer_slug is not None:
                by_developer.setdefault(offer.developer_slug, []).append(offer)
        ranked = sorted(by_developer, key=lambda slug: (-len(by_developer[slug]), slug))
        ranked = ranked[: criteria.top.value]
        return MarketStatistics(
            criteria=criteria,
            offers=len(found),
            investments=len({o.investment_slug for o in found if o.investment_slug is not None}),
            developers=len(by_developer),
            price_spread=Spread.of([o.price for o in found if o.price is not None]),
            price_per_m2_spread=Spread.of(_prices_per_m2(found)),
            area_spread=Spread.of([o.area_m2 for o in found if o.area_m2]),
            top_developers=tuple(_share(slug, by_developer[slug]) for slug in ranked),
        )


def _within(value: float | None, bounds: PriceRange | AreaRange | None) -> bool:
    if bounds is None:
        return True
    if value is None:
        return False
    low = bounds.low is None or value >= bounds.low.value
    high = bounds.high is None or value <= bounds.high.value
    return low and high


def _prices_per_m2(offers: Sequence[MarketOffer]) -> list[float]:
    return [value for offer in offers if (value := offer.price_per_m2) is not None]


def _share(slug: str, offers: Sequence[MarketOffer]) -> DeveloperShare:
    per_m2 = sorted(_prices_per_m2(offers))
    return DeveloperShare(
        developer_slug=slug,
        offers=len(offers),
        investments=len({o.investment_slug for o in offers if o.investment_slug is not None}),
        median_price_per_m2=Spread.quantile(per_m2, 0.5) if per_m2 else None,
    )
