"""Every active offer of a city with the investments they belong to (D15).

``OfferSnapshotDto``: ``GET /api/map/offer-snapshot/{citySlug}`` [P 2026-10-30] (sample
``api.offer_snapshot_wroclaw``, tests/fixtures/api/offer_snapshot_*.json): each offer a
row of numbers (``SNAPSHOT_COLUMNS``), read into ``CitySalesDto``.

``CitySalesDto``: the offers with named fields, the shape of the service's former
``/api/offers/city-sales/{citySlug}`` (sample ``api.city_sales_sopot``), gone since the 2.0
build of 2026-10-29.
"""

from typing import Any

from pydantic import field_validator

from deweloperuch_mcp.api.dto.dto import Dto, Number
from deweloperuch_mcp.models.market_statistics import CityOffers, MarketOffer
from deweloperuch_mcp.models.offer import ACTIVE
from deweloperuch_mcp.models.values import CitySlug


class CitySalesInvestmentDto(Dto):
    id: int
    slug: str
    developerSlug: str | None = None
    status: str | None = None


class CitySaleDto(Dto):
    """One active offer, compact: ``priceSqm`` is ``amount / size`` to 0.01 [P 2026-10-13,
    tests/fixtures/api/city_sales_krakow.json], so it is not read (the domain derives it)."""

    id: int
    investId: int | None
    amount: Number | None
    size: Number | None
    status: str

    def to_model(self, investment: CitySalesInvestmentDto | None) -> MarketOffer:
        """The offer with the slugs of ``investment`` (``None``: not on the city's list)."""
        return MarketOffer(
            offer_id=self.id,
            investment_slug=None if investment is None else investment.slug,
            developer_slug=None if investment is None else self._text(investment.developerSlug),
            status=self.status,
            price=self._number(self.amount),
            area_m2=self._number(self.size),
        )


class CitySalesDto(Dto):
    investments: list[CitySalesInvestmentDto]
    sales: list[CitySaleDto]

    def to_model(self, city: CitySlug) -> CityOffers:
        """Each offer with the slugs of its investment and developer (``None`` when its
        investment is not on the city's list)."""
        investments = {item.id: item for item in self.investments}
        return CityOffers(
            city=city,
            offers=tuple(
                sale.to_model(None if sale.investId is None else investments.get(sale.investId))
                for sale in self.sales
            ),
        )


# [P 2026-10-30] `wroclaw`: 5836 rows of 7 numbers. [0] offer id, [1] investment id (one of
# `investments[].id`), [2] status (0 in every row; the page counts all 5836 as active),
# [3] amount PLN, [4] PLN/m² (= [3] / [5] in every row, not read), [5] area m², [6] change
# since the first price in PLN (not read).
SNAPSHOT_COLUMNS = {"id": 0, "investId": 1, "status": 2, "amount": 3, "size": 5}
SNAPSHOT_ROW_LENGTH = 7
SNAPSHOT_STATUS: dict[object, str] = {0: ACTIVE}
"""Status codes of a snapshot row; [W] what other codes mean (none seen), kept as text."""


class OfferSnapshotDto(Dto):
    """``GET /api/map/offer-snapshot/{citySlug}`` [P 2026-10-30]. ``asOf`` (the day of the
    snapshot) is not read: the market summary has no date."""

    investments: list[CitySalesInvestmentDto]
    sales: list[list[Number | None]]

    @field_validator("sales")
    @classmethod
    def _rows(cls, rows: list[list[Number | None]]) -> list[list[Number | None]]:
        for row in rows:
            if len(row) < SNAPSHOT_ROW_LENGTH:
                raise ValueError(
                    f"wiersz oferty ma {len(row)} pól, oczekiwano {SNAPSHOT_ROW_LENGTH}"
                )
        return rows

    def city_sales(self, source: str) -> CitySalesDto:
        """The offers as ``CitySalesDto`` rows (named fields); ``source`` for its errors."""
        sales: list[dict[str, Any]] = []
        for row in self.sales:
            sale = {name: row[index] for name, index in SNAPSHOT_COLUMNS.items()}
            sale["status"] = SNAPSHOT_STATUS.get(sale["status"], str(sale["status"]))
            sales.append(sale)
        data = {"investments": [item.model_dump() for item in self.investments], "sales": sales}
        return Dto.validated(CitySalesDto, data, source)
