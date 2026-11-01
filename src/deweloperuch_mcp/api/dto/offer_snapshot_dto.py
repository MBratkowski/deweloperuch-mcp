"""``OfferSnapshotDto``: ``GET /api/map/offer-snapshot/{citySlug}`` [P 2026-10-31]
(docs/discovery/endpoints.md section 2; tests/fixtures/api/offer_snapshot_*_20261031.json),
every active offer of a city in compact rows, with the investments they belong to (D20).

Only what the market summary counts and shows is read: the city the snapshot is of, the
day of the data, each investment's slugs and developer's name, and per offer its id,
investment, price and area.
"""

from typing import Any

from pydantic import ValidationError, ValidatorFunctionWrapHandler, field_validator, model_validator

from deweloperuch_mcp.api.dto.dto import DateText, Dto, Number
from deweloperuch_mcp.models.market_statistics import CityOffers, MarketOffer
from deweloperuch_mcp.models.values import CitySlug

SALE_ITEMS = 7
"""[P 2026-10-31] the items of every sale row (11,672 of Warszawa, 8 of Sopot):
``[sale_id, invest_id, 0, amount, price per m², size, start_amount_difference]``."""


class OfferSnapshotInvestmentDto(Dto):
    """An investment of the city: ``id`` is the ``invest_id`` the sales name;
    ``developer`` is its developer's name [P 2026-10-31: on every investment of both
    fixtures, one name per ``developerSlug``]."""

    id: int
    slug: str
    developerSlug: str | None = None
    developer: str | None = None


class OfferSnapshotSaleDto(Dto):
    """One active offer, sent as a row of numbers without keys and read by position
    ([P 2026-10-31] endpoints.md section 2: positions 0, 1, 3 and 5 equal ``sale_id``,
    ``invest_id``, ``amount`` and ``size`` of the offer list, 125 rows of 125).

    Not read: position 2, a constant 0 of unknown meaning (T76); position 4, the price per
    m², which is ``amount / size`` to 0.01 [P 2026-10-31], so the domain derives it as for
    search results; position 6, the change since the first price, which the summary does
    not use. Only an array of exactly ``SALE_ITEMS`` is read by position: anything else is a
    changed service (``UnexpectedResponseError``, D21), never an offer read from the wrong
    places. A ``null`` investment, price or area (never seen) is no value, as ``""`` is.
    """

    id: int
    investId: int | None
    amount: Number | None
    size: Number | None

    @model_validator(mode="before")
    @classmethod
    def _by_position(cls, row: Any) -> Any:
        if not isinstance(row, list) or len(row) != SALE_ITEMS:
            raise ValueError(f"oczekiwano tablicy {SALE_ITEMS} wartości")
        return {"id": row[0], "investId": row[1], "amount": row[3], "size": row[5]}

    def to_model(self, investment: OfferSnapshotInvestmentDto | None) -> MarketOffer:
        """The offer with the slugs and the developer's name of ``investment`` (``None``:
        none, or not on the city's list)."""
        return MarketOffer(
            offer_id=self.id,
            investment_slug=None if investment is None else self._text(investment.slug),
            developer_slug=None if investment is None else self._text(investment.developerSlug),
            developer_name=None if investment is None else self._text(investment.developer),
            price=self._positive(self.amount),
            area_m2=self._positive(self.size),
        )


class OfferSnapshotDto(Dto):
    citySlug: str
    """The city the snapshot is of: the slug asked for [P 2026-10-31, both fixtures];
    ``OfferSnapshotApi`` compares them."""
    asOf: DateText | None = None
    """The day of the data [P 2026-10-31]: Cloudflare may serve a copy more than half a
    day old, so this, not the day of the request, is the day to show (endpoints.md). It is
    only shown, so one that cannot be read is left out (``None``), not a failed summary."""
    investments: list[OfferSnapshotInvestmentDto]
    sales: list[OfferSnapshotSaleDto]

    @field_validator("asOf", mode="wrap")
    @classmethod
    def _day_or_none(cls, value: Any, handler: ValidatorFunctionWrapHandler) -> Any:
        try:
            return handler(value)
        except ValidationError:
            return None

    def to_model(self, city: CitySlug) -> CityOffers:
        """Each offer with the slugs of its investment and developer (``None`` when it has
        no investment or one not on the city's list), as of the snapshot's day."""
        investments = {item.id: item for item in self.investments}
        return CityOffers(
            city=city,
            offers=tuple(
                sale.to_model(None if sale.investId is None else investments.get(sale.investId))
                for sale in self.sales
            ),
            as_of=self._day(self.asOf),
        )
