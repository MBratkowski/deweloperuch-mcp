"""``TransactionStatsPageDto``: the prop ``view`` of the transaction statistics page of a
city, ``/statystyki/{city}/transakcje`` (RSC) [P 2026-10-31], every month of the
transactions of flats in the city on the secondary market.

[P 2026-10-31] tests/fixtures/rsc/stats_tx_warszawa_20261031.rsc and
stats_tx_karpacz_20261031.rsc (sample page.stats_transactions.v2_view, docs/discovery/
pages-rsc.md, the ``transakcje`` section): ``view.monthly`` has one row a month from
2017-01 to the current month, without a gap (118 rows on both pages). A month with
transactions has 10 keys; a month without any has 8 (no ``secondary_count``, no
``unknown_count``) with every measure 0. The other keys of ``view`` (``anchor``,
``quarterly``, ``slices``...) and the page's other props (``latestSummary``...) are not
read.
"""

from typing import Self

from pydantic import model_validator

from deweloperuch_mcp.api.dto.dto import Dto, MonthText, Number
from deweloperuch_mcp.api.dto.transaction_period_dto import TransactionPeriodDto
from deweloperuch_mcp.models.errors import UnexpectedResponseError
from deweloperuch_mcp.models.transaction_series import TransactionPeriod

OTHER_MARKET = (
    "Miesięczne dane serwisu obejmują też transakcje spoza rynku wtórnego, a to narzędzie "
    "podaje tylko rynek wtórny, więc nie zwraca tego szeregu. To nie znaczy, że argumenty są "
    "błędne: nie zmieniaj ich i nie ponawiaj wywołania, powiedz o tym użytkownikowi. "
    "Kwartały (granularity=quarter) idą z innego źródła, ale ich rynek jest nieokreślony."
)
"""Why the months of a city are not given: some of their transactions are of another
market than the one the tools describe (not a changed service, not wrong arguments)."""


class TransactionStatsMonthDto(TransactionPeriodDto):
    """A month of ``view.monthly`` [P 2026-10-31]: every field is on both pages."""

    month: MonthText
    transaction_count: int
    secondary_count: int | None = None
    """Absent in a month without transactions, and only there."""
    med_price_sqm: Number | None
    avg_price_sqm: Number | None
    med_size: Number | None
    avg_size: Number | None
    med_amount: Number | None
    avg_amount: Number | None

    @model_validator(mode="after")
    def _of_the_secondary_market(self) -> Self:
        """Every transaction of the month is of the secondary market, as the tools say
        (D12).

        [P 2026-10-31] ``secondary_count`` equals ``transaction_count`` in all 114 months of
        Warsaw and all 67 of Karpacz with transactions, and is absent in the months without
        any; the page's lead says „…na rynku wtórnym…”, its ``isMixedMarket`` is false, and
        its client labels the series „rynek wtórny” [P z kodu 2026-10-30]. [W] the name:
        ``secondary_count`` counts the transactions of the secondary market.

        - fewer of them than all transactions: the month has transactions of another
          market, so the series is not the one described (``OTHER_MARKET``); raised as
          itself, pydantic does not wrap it, and inside the transport's decode, so the page
          is not cached;
        - absent in a month with transactions, or more of them than all: the page no longer
          says which market (a contract mismatch, ``ValueError``), never read as 0.

        ``unknown_count`` (0 in those months) is not read: a transaction of an unknown
        market would make the two counts differ.
        """
        secondary, count = self.secondary_count, self.transaction_count
        if secondary is None:
            if count > 0:
                raise ValueError(f"{self.month}: brak liczby transakcji z rynku wtórnego")
        elif secondary > count:
            raise ValueError(f"{self.month}: {secondary} z {count} transakcji z rynku wtórnego")
        elif secondary < count:
            raise UnexpectedResponseError(
                OTHER_MARKET,
                detail=(
                    f"prop view, miesiąc {self.month}: {secondary} z {count} transakcji z rynku "
                    "wtórnego"
                ),
            )
        return self

    def to_model(self) -> TransactionPeriod:
        # [W] `med_*` is read as the median and `avg_*` as the mean (their names, and the
        # page's lead: „Mediany cen transakcyjnych…”). [P 2026-10-31] they differ in every
        # month of Warsaw with transactions and are equal in the months of Karpacz with one
        # or two, as a median and a mean of so few are.
        count = self.transaction_count
        return TransactionPeriod(
            period=self.month,
            transactions=count,
            median_price_per_m2=self._measure(count, self.med_price_sqm),
            average_price_per_m2=self._measure(count, self.avg_price_sqm),
            median_area_m2=self._measure(count, self.med_size),
            average_area_m2=self._measure(count, self.avg_size),
            median_price=self._measure(count, self.med_amount),
            average_price=self._measure(count, self.avg_amount),
        )


class TransactionStatsPageDto(Dto):
    """The prop ``view`` of the page: only its months (``monthly``) are read."""

    monthly: list[TransactionStatsMonthDto]

    def to_model(self) -> tuple[TransactionPeriod, ...]:
        """The months in the page's order, up to the newest one with transactions.

        [P 2026-10-31] the page pads its end with empty months up to the current one
        (Warszawa 2026-08..2026-10, 3 months; Karpacz 2026-01..2026-10, 10), while the JSON
        series of 1.0 ended with the newest month with transactions [P 2026-10-15/16,
        tests/fixtures/api/monthly_tx_*.json: Warsaw 2026-07, Karpacz 2025-12]. A month
        after it cannot be told from a month not yet in the register, so it is dropped;
        the empty months before it are kept (Warsaw 2026-06). A page without any
        transaction gives no month: the domain reports a city without data.
        """
        months = [row.to_model() for row in self.monthly]
        newest = max((item.period for item in months if item.transactions > 0), default="")
        return tuple(item for item in months if item.period <= newest)
