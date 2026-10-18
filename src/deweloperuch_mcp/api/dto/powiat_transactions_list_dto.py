"""``PowiatTransactionsListDto``: ``GET /api/map/powiat-stats`` [P] (sample
``api.powiat_stats``), the transactions of every powiat.

Read like ``CityTransactionsListDto``: no ``*_change`` (T10, [H]), ``avg_*`` as the
service gives them (averages or medians, T10), and a 0 in them is no value.
"""

from pydantic import ConfigDict, RootModel

from deweloperuch_mcp.api.dto.dto import Dto, Number
from deweloperuch_mcp.models.location_ranking import LocationTransactions


class PowiatTransactionsDto(Dto):
    """One powiat of ``PowiatTransactionsListDto`` [P]."""

    powiat_rcn_id: int
    nazwa: str
    transaction_count: int
    avg_price_sqm: Number | None
    avg_size: Number | None
    avg_amount: Number | None

    def to_model(self) -> LocationTransactions:
        # [W] by analogy with the cities: no powiat had a 0 on 2026-10-15 (380 powiats,
        # tests/fixtures/api/powiat_stats_20261015.json [P 2026-10-15]), but the same
        # service writes 0 for no value in the ranking of cities, so a 0 here is no value too
        # (tests/unit/api/dto/test_powiat_transactions_list_dto.py).
        return LocationTransactions(
            name=self.nazwa,
            powiat_id=self.powiat_rcn_id,
            transaction_count=self.transaction_count,
            price_per_m2=self._positive(self.avg_price_sqm),
            area_m2=self._positive(self.avg_size),
            price=self._positive(self.avg_amount),
        )


class PowiatTransactionsListDto(RootModel[list[PowiatTransactionsDto]]):
    """Every powiat (369 in the sample ``api.powiat_stats``, 380 on 2026-10-15)."""

    model_config = ConfigDict(frozen=True)

    def to_model(self) -> tuple[LocationTransactions, ...]:
        return tuple(row.to_model() for row in self.root)
