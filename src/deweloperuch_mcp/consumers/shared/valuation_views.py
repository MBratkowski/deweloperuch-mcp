"""The views of a valuation (``estimate_property_value``), for the CLI (``--json``) and for
the MCP presenter. Each builds itself from the use case's result (``from_result``) or a
model (``from_model``). Names are the models' (D3): no backend names and no backend
values; numbers are ``float`` (PLN, m², metres), dates ``datetime.date``, missing values
``None``.
"""

import datetime as dt
from typing import Self

from deweloperuch_mcp.consumers.shared.view import View
from deweloperuch_mcp.models.valuation import ComparableTransaction, PricePerM2Stats
from deweloperuch_mcp.usecases.estimate_property_value import EstimatePropertyValueResult


class ComparableTransactionView(View):
    """A sale of a flat near the valued point that the service compared it with."""

    address: str | None = None
    """Street and number of the building."""
    date: dt.date | None = None
    price: float | None = None
    """The price paid, in PLN."""
    area_m2: float | None = None
    price_per_m2: float | None = None
    floor: int | None = None
    distance_m: float | None = None
    """From the valued point, in metres, rounded by the service to the nearest 50 m."""
    market: str | None = None
    """``primary`` or ``secondary``."""
    building_slug: str | None = None
    """What get_building takes."""
    city_slug: str | None = None

    @classmethod
    def from_model(cls, item: ComparableTransaction) -> Self:
        return cls(
            address=item.address,
            date=item.date,
            price=item.price,
            area_m2=item.area_m2,
            price_per_m2=item.price_per_m2,
            floor=item.floor,
            distance_m=item.distance_m,
            market=item.market,
            building_slug=item.building_slug,
            city_slug=item.city_slug,
        )


class PricePerM2StatsView(View):
    """Statistics of prices per m² (PLN) as the service gives them."""

    count: int | None = None
    median_price_per_m2: float | None = None
    average_price_per_m2: float | None = None
    min_price_per_m2: float | None = None
    max_price_per_m2: float | None = None

    @classmethod
    def from_model(cls, stats: PricePerM2Stats) -> Self:
        return cls(
            count=stats.count,
            median_price_per_m2=stats.median_price_per_m2,
            average_price_per_m2=stats.average_price_per_m2,
            min_price_per_m2=stats.min_price_per_m2,
            max_price_per_m2=stats.max_price_per_m2,
        )


class ValuationView(View):
    """The value of a flat estimated from the transactions nearby: an approximation, not
    an appraisal (``estimate_property_value``)."""

    lat: float
    lng: float
    area_m2: float
    address: str | None = None
    estimated_value: float | None
    """In PLN; ``None`` when the service gave no estimate."""
    low_confidence: bool | None = None
    """Whether the estimate is to be given only with a caveat (``hint``): fewer than 5
    comparable transactions; ``None`` without an estimate."""
    price_per_m2: float | None
    radius_m: int | None
    """How far from the point the comparable transactions are."""
    period_months: int | None
    """How many of the latest months they come from."""
    stats: PricePerM2StatsView | None
    comparables_total: int
    """Every comparable transaction the service gave."""
    comparables_omitted: int
    """Comparable transactions left out because of ``limit``."""
    hint: str | None = None
    comparables: list[ComparableTransactionView]
    """The nearest first; at most ``limit`` of them."""

    @classmethod
    def from_result(cls, found: EstimatePropertyValueResult) -> Self:
        listing = found.listing
        shown = listing.valuation
        subject = shown.subject
        return cls(
            lat=subject.point.lat,
            lng=subject.point.lng,
            area_m2=subject.area.value,
            address=None if subject.address is None else subject.address.text,
            estimated_value=shown.estimated_value,
            low_confidence=shown.low_confidence if shown.estimated else None,
            price_per_m2=shown.price_per_m2,
            radius_m=shown.radius_m,
            period_months=shown.period_months,
            stats=None if shown.stats is None else PricePerM2StatsView.from_model(shown.stats),
            comparables_total=listing.total,
            comparables_omitted=listing.omitted,
            hint=found.hint,
            comparables=[
                ComparableTransactionView.from_model(item) for item in listing.comparables
            ],
        )
