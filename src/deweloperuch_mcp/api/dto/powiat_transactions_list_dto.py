"""``PowiatTransactionsListDto``: ``GET /api/map/powiat-stats`` [P] (sample
``api.powiat_stats``), the transactions of every powiat.

Read like ``CityTransactionsListDto``: no ``*_change`` (T10, [H]), and ``avg_*`` as the
service gives them (averages or medians, T10).
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
        return LocationTransactions(
            name=self.nazwa,
            powiat_id=self.powiat_rcn_id,
            transaction_count=self.transaction_count,
            price_per_m2=self._number(self.avg_price_sqm),
            area_m2=self._number(self.avg_size),
            price=self._number(self.avg_amount),
        )


class PowiatTransactionsListDto(RootModel[list[PowiatTransactionsDto]]):
    """Every powiat (369 in the sample ``api.powiat_stats``)."""

    model_config = ConfigDict(frozen=True)

    def to_model(self) -> tuple[LocationTransactions, ...]:
        return tuple(row.to_model() for row in self.root)
