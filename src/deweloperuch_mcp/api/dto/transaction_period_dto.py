"""``TransactionPeriodDto``: what a period of the transaction statistics shares, a month of
``MonthlyTransactionStatsDto`` and a quarter of ``CityTrendDto``: how a price or an area is
read."""

from deweloperuch_mcp.api.dto.dto import Dto


class TransactionPeriodDto(Dto):
    """The base of a period's DTO; subclasses read their measures with ``_measure`` in
    ``to_model()``."""

    @classmethod
    def _measure(cls, transactions: int, value: int | float | str | None) -> float | None:
        """A price or an area, or ``None`` when the service has none to give.

        [P 2026-10-13] live observation (Warsaw, months 2026-05 and 2026-06): a period
        without transactions comes with every median and mean as 0, not ``null``. No flat
        has a price or an area of 0, so a period without transactions has no measures, and
        any 0 (or less) is a missing value, never a price.
        """
        measured = cls._number(value)
        if transactions <= 0 or measured is None or measured <= 0:
            return None
        return measured
