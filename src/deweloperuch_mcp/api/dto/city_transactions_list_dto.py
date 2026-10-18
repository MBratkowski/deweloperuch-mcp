"""``CityTransactionsListDto``: ``GET /api/city-transaction-stats`` [P] (sample
``api.city_tx_stats``), the transactions of every city, towns and villages included.

Only what the ranking uses is read. ``*_change`` (``transaction_count_change``,
``price_sqm_change``...) is never read: its period and base are [H] (open question T10),
and so is the period of the counts. ``avg_price_sqm``, ``avg_size`` and ``avg_amount`` may
hold medians ([H], T10): the model calls them the price per m², area and price as the
service gives them. A 0 in them is no value (``Dto._positive``): ``Ignatki-osiedle`` has 8
transactions and 0 for all three [P 2026-10-15]
(tests/fixtures/api/city_tx_stats_20261015.json), so it has no price and ranks last by
price instead of first.
"""

from pydantic import ConfigDict, RootModel

from deweloperuch_mcp.api.dto.dto import Dto, Number
from deweloperuch_mcp.models.location_ranking import LocationTransactions


class CityTransactionsDto(Dto):
    """One city of ``CityTransactionsListDto`` [P]."""

    city: str
    city_slug: str | None
    transaction_count: int
    avg_price_sqm: Number | None
    avg_size: Number | None
    avg_amount: Number | None

    def to_model(self) -> LocationTransactions:
        return LocationTransactions(
            name=self.city,
            city_slug=self._text(self.city_slug),
            transaction_count=self.transaction_count,
            price_per_m2=self._positive(self.avg_price_sqm),
            area_m2=self._positive(self.avg_size),
            price=self._positive(self.avg_amount),
        )


class CityTransactionsListDto(RootModel[list[CityTransactionsDto]]):
    """Every city (2 448 in the sample ``api.city_tx_stats``, 548 KB; 2 529 on
    2026-10-15)."""

    model_config = ConfigDict(frozen=True)

    def to_model(self) -> tuple[LocationTransactions, ...]:
        return tuple(row.to_model() for row in self.root)
