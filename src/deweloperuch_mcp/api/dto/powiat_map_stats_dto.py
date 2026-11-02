"""``PowiatMapStatsDto``: ``GET /api/statystyki/powiat-map-stats`` [P 2026-11-01] (sample
``api.powiat_map_stats``), the transactions of every powiat on three markets over one
12-month window.

Only what the ranking uses is read: ``periodStart`` and ``periodEndMonth`` (the window,
``2025-11-01`` to ``2026-10``) and, for each row, ``id`` and the market objects ``wtorny``
(secondary), ``pierwotny`` (primary) and ``oba`` (both) with ``n`` (transactions), ``m2``
(price per m²), ``price`` and ``size`` (area). A missing market is ``null``, never ``n: 0``
[P 2026-11-01]: such a powiat is not ranked on that market. ``primary`` is not read: its
base differs from the ``n`` shown (T86), and neither are ``def``, ``q``, ``w``, ``v``,
``all``, ``own``, ``quarterStart`` and ``windowEnd`` (internal to the service's map).
Whether ``m2``, ``price`` and ``size`` are medians or means is open (T85): the model calls
them the price per m², price and area as the service gives them.

``oba`` is not the sum of the other two (equal ``n`` in 80 of 303 rows [P 2026-11-01],
T86): it is read as the service's own figures for both markets. The rows name no powiat:
the names come from the packaged table (``PlaceNamesDto``), every id of the capture of
2026-11-02 included.
"""

from typing import Annotated

from pydantic import StringConstraints

from deweloperuch_mcp.api.dto.dto import Dto, Number
from deweloperuch_mcp.models.location_ranking import (
    LocationTransactions,
    PlaceNames,
    PowiatTransactions,
    RankingMarket,
    TransactionPeriod,
)

FirstDay = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^\d{4}-\d{2}-01$")]
Month = Annotated[str, StringConstraints(strip_whitespace=True, pattern=r"^\d{4}-\d{2}$")]


class PowiatMarketDto(Dto):
    """One market of one powiat [P 2026-11-01]: no other key than these and ``primary``."""

    n: int
    m2: Number | None
    price: Number | None
    size: Number | None

    def to_model(self, *, name: str, powiat_id: int) -> LocationTransactions:
        # [W] by analogy with the city ranking: a 0 is no value (Dto._positive); no market
        # object had a 0 or a null price on 2026-11-02 (tests/contract/api/dto/
        # test_powiat_map_stats_dto.py).
        return LocationTransactions(
            name=name,
            powiat_id=powiat_id,
            transaction_count=self.n,
            price_per_m2=self._positive(self.m2),
            area_m2=self._positive(self.size),
            price=self._positive(self.price),
        )


class PowiatRowDto(Dto):
    """One powiat: its id (``powiatId`` of ``map/tx-cities``) and its three markets, each an
    object or ``null`` (the keys are present in every row [P 2026-11-01])."""

    id: int
    wtorny: PowiatMarketDto | None
    pierwotny: PowiatMarketDto | None
    oba: PowiatMarketDto | None

    def markets(self) -> dict[RankingMarket, PowiatMarketDto | None]:
        return {
            RankingMarket.SECONDARY: self.wtorny,
            RankingMarket.PRIMARY: self.pierwotny,
            RankingMarket.ALL: self.oba,
        }


class PowiatMapStatsDto(Dto):
    """Every powiat (380 on 2026-11-01 and 2026-11-02) and the window of their figures."""

    periodStart: FirstDay
    periodEndMonth: Month
    rows: list[PowiatRowDto]

    def to_model(self, names: PlaceNames) -> PowiatTransactions:
        markets: dict[RankingMarket, list[LocationTransactions]] = {m: [] for m in RankingMarket}
        for row in self.rows:
            name = names.powiat(row.id)
            for market, figures in row.markets().items():
                if figures is not None:
                    markets[market].append(figures.to_model(name=name, powiat_id=row.id))
        return PowiatTransactions(
            period=TransactionPeriod(start=self.periodStart, end=self.periodEndMonth),
            powiats=len(self.rows),
            markets={market: tuple(places) for market, places in markets.items()},
        )
