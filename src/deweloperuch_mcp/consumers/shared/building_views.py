"""The views of a building (``get_building``), for the CLI (``--json``) and for the MCP
presenter, which cuts them down for a model. Each builds itself from the use case's
result (``from_result``) or a model (``from_model``). Names are the models' (D3): no
backend names and no backend values; numbers are ``float`` (PLN, m²), dates
``datetime.date``, missing values ``None``. ``building_url`` is the building's page on
the service, for people (D12).
"""

import datetime as dt
from typing import Self

from deweloperuch_mcp.consumers.shared.view import View
from deweloperuch_mcp.models.building import NeighbourhoodTrend, Transaction, Unit
from deweloperuch_mcp.usecases.get_building import GetBuildingResult


class TransactionView(View):
    """One sale of a unit, as the price register recorded it."""

    date: dt.date | None
    price: float | None
    """The price of the deed, in ``currency``."""
    price_per_m2: float | None
    currency: str | None = None
    market: str | None = None
    """``primary`` or ``secondary``."""
    classification: str | None = None
    """``regular``, ``share``, ``bulk``, ``government``, ``enforcement``, ``discount``,
    ``anomaly_low`` or ``anomaly_high``."""
    buyer: str | None = None
    """``natural_person`` or ``legal_person``."""
    seller: str | None = None
    share: str | None = None
    """The fraction of the unit sold; ``1/1`` is the whole unit."""

    @classmethod
    def from_model(cls, transaction: Transaction) -> Self:
        return cls(
            date=transaction.date,
            price=transaction.price,
            price_per_m2=transaction.price_per_m2,
            currency=transaction.currency,
            market=transaction.market,
            classification=transaction.classification,
            buyer=transaction.buyer,
            seller=transaction.seller,
            share=transaction.share,
        )


class UnitView(View):
    """A unit (a flat) with its transactions, oldest first."""

    unit_id: int
    name: str
    """The register's designation of the unit."""
    floor: int | None = None
    rooms: int | None = None
    area_m2: float | None = None
    transactions: list[TransactionView]

    @classmethod
    def from_model(cls, unit: Unit) -> Self:
        return cls(
            unit_id=unit.unit_id,
            name=unit.name,
            floor=unit.floor,
            rooms=unit.rooms,
            area_m2=unit.area_m2,
            transactions=[TransactionView.from_model(t) for t in unit.transactions],
        )


class TrendQuarterView(View):
    period: str
    """``2025-Q3``."""
    avg_price_per_m2: float | None
    transactions: int | None = None


class NeighbourhoodTrendView(View):
    """The price per m² of the transactions within ``radius_km`` of the building."""

    radius_km: float | None
    quarters_total: int
    """Every quarter the service has."""
    quarters_omitted: int
    """Older quarters left out."""
    quarters: list[TrendQuarterView]
    """Oldest first."""

    @classmethod
    def from_model(cls, trend: NeighbourhoodTrend) -> Self:
        return cls(
            radius_km=trend.radius_km,
            quarters_total=trend.total,
            quarters_omitted=trend.omitted,
            quarters=[
                TrendQuarterView(
                    period=quarter.period,
                    avg_price_per_m2=quarter.avg_price_per_m2,
                    transactions=quarter.transactions,
                )
                for quarter in trend.quarters
            ],
        )


class BuildingView(View):
    """A building of the price register with its units (``get_building``)."""

    building_slug: str
    name: str | None = None
    """The address; ``None`` when the register gives none."""
    building_url: str | None = None
    """The building's page on the service."""
    city: str
    city_slug: str
    street: str | None = None
    lat: float | None = None
    lng: float | None = None
    avg_price: float | None = None
    """The mean transaction price, as the service counts it."""
    avg_area_m2: float | None = None
    avg_price_per_m2: float | None = None
    units_total: int
    transactions_total: int
    non_regular_transactions: dict[str, int]
    """The transactions of the whole building that are no regular sale, by class (the
    words of ``TransactionView.classification``), the most frequent first; ``{}``: none."""
    first_transaction_date: dt.date | None = None
    last_transaction_date: dt.date | None = None
    units: list[UnitView]
    """The units whose last transaction is the newest first; at most ``limit``."""
    units_omitted: int
    """Units left out because of ``limit``."""
    hint: str | None = None
    """What the numbers alone do not say, e.g. that the trend has no quarters."""
    neighbourhood_trend: NeighbourhoodTrendView | None = None
    """Only when asked for."""

    @classmethod
    def from_result(cls, found: GetBuildingResult) -> Self:
        listing = found.listing
        shown = listing.building
        return cls(
            building_slug=shown.building_slug,
            name=shown.name,
            building_url=found.building_url,
            city=shown.city,
            city_slug=shown.city_slug,
            street=shown.street,
            lat=shown.lat,
            lng=shown.lng,
            avg_price=shown.avg_price,
            avg_area_m2=shown.avg_area_m2,
            avg_price_per_m2=shown.avg_price_per_m2,
            units_total=len(shown.units),
            transactions_total=shown.transactions_count,
            non_regular_transactions=shown.non_regular_transactions(),
            first_transaction_date=shown.first_sold_on,
            last_transaction_date=shown.last_sold_on,
            units=[UnitView.from_model(unit) for unit in listing.units],
            units_omitted=listing.omitted,
            hint=found.hint,
            neighbourhood_trend=(
                None if found.trend is None else NeighbourhoodTrendView.from_model(found.trend)
            ),
        )
