"""``StandaloneValuationDto``: ``GET /api/standalone-valuation`` [P] (docs/discovery/
endpoints.md, "5. Valuation"; samples ``api.standalone_val`` (the API) and
``page.offer_report`` (prop ``data``, the same format, [P] pages-rsc.md)), with its
statistics (``ValuationStatsDto``) and comparable transactions
(``ValuationTransactionDto``).

The response (about 180 KB) is mostly the service's working data: ``radiusPool`` (279
entries in the sample), ``estimationContext`` and ``buildings``. The DTOs do not read
them, so they never reach the models nor a result (D5); neither do fields whose meaning
is not confirmed (``trendMonthlyPct``, ``areaElasticity``, ``radiusLevel``: only its
values ``sasiedztwo`` and ``okolica`` are, ``buildingTransactionCount``, and of a
transaction ``excluded`` and ``isSamePrimaryInvestment``) nor the register's ids of units
(``unitNumber``, ``saleRcnId``). ``radiusCeilingM`` is read with its meaning [W] (the
widest radius, ``Valuation.at_widest_radius``). Fields the models read are required where
the contract tests rely on them, so a renamed one fails them.
"""

from deweloperuch_mcp.api.dto.dto import DateText, Dto, Number
from deweloperuch_mcp.models.valuation import (
    PRIMARY,
    SECONDARY,
    ComparableTransaction,
    PricePerM2Stats,
    Valuation,
    ValuationSubject,
)

_MARKETS = {"pierwotny": PRIMARY, "wtorny": SECONDARY}
"""``marketType`` [P] (docs/discovery/entities.md)."""


class ValuationTransactionDto(Dto):
    """One of ``transactions``: a comparable transaction."""

    address: str | None = None
    area: Number | None
    pricePerSqm: Number | None
    totalPrice: Number | None
    date: DateText | None
    floor: int | float | str | None = None
    """``"6"`` in the samples; anything else is read as no floor rather than refused."""
    distance: Number | None
    marketType: str | None = None
    investRcnSlug: str | None = None
    investRcnCitySlug: str | None = None

    def to_model(self) -> ComparableTransaction:
        return ComparableTransaction(
            address=self._text(self.address),
            date=self._day(self.date),
            price=self._number(self.totalPrice),
            area_m2=self._number(self.area),
            price_per_m2=self._number(self.pricePerSqm),
            floor=self._floor(self.floor),
            # [P] metres rounded to the nearest 50 m, in both samples: api.standalone_val
            # 150, 152 and 165 m (haversine) -> 150; page.offer_report 42 -> 50, 93.5 and
            # 119.8 -> 100.
            distance_m=self._number(self.distance),
            market=self._market(self.marketType),
            building_slug=self._text(self.investRcnSlug),
            city_slug=self._text(self.investRcnCitySlug),
        )

    @staticmethod
    def _floor(value: int | float | str | None) -> int | None:
        """``"6"``, ``"-1"`` or ``6`` -> a whole number; anything else -> ``None``."""
        if isinstance(value, bool) or value is None:
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return int(value) if value.is_integer() else None
        stripped = value.strip()
        unsigned = stripped[1:] if stripped[:1] in ("+", "-") else stripped
        return int(stripped) if unsigned.isascii() and unsigned.isdecimal() else None

    @classmethod
    def _market(cls, value: str | None) -> str | None:
        """``pierwotny`` -> ``primary``, ``wtorny`` -> ``secondary``; others lowercased."""
        raw = cls._text(value)
        return None if raw is None else _MARKETS.get(raw, raw.lower())


class ValuationStatsDto(Dto):
    averagePricePerSqm: Number | None
    medianPricePerSqm: Number | None
    minPricePerSqm: Number | None
    maxPricePerSqm: Number | None
    count: Number | None

    def to_model(self) -> PricePerM2Stats:
        # [W] the service's own figures: in both samples ``count`` is the number of
        # transactions (9, 26) and none is ``excluded``, so whether excluded ones count is
        # not known. A price of 0 is none (``_positive``); a count of 0 is a count, one
        # below 0 is none.
        count = self._rounded(self.count)
        return PricePerM2Stats(
            count=None if count is None or count < 0 else count,
            median_price_per_m2=self._positive(self.medianPricePerSqm),
            average_price_per_m2=self._positive(self.averagePricePerSqm),
            min_price_per_m2=self._positive(self.minPricePerSqm),
            max_price_per_m2=self._positive(self.maxPricePerSqm),
        )


class StandaloneValuationDto(Dto):
    """``GET /api/standalone-valuation`` [P] (sample ``api.standalone_val``)."""

    estimatedValue: Number | None
    estimatedPricePerSqm: Number | None
    radiusKm: Number | None
    radiusCeilingM: Number | None
    periodMonths: Number | None
    stats: ValuationStatsDto | None
    transactions: list[ValuationTransactionDto]

    def to_model(self, subject: ValuationSubject) -> Valuation:
        """The estimate for ``subject`` (what was asked for) with every comparable
        transaction, in the service's order.

        The value and the price per m² are one estimate: both or neither ([P] both
        samples, asked for a whole 50 m², give them together, the value being the price
        per m² times that area; which area a fractional request is valued at is not
        confirmed, T41). A price of 0 or less is none (``_positive``): never seen here
        ([H] that the service sends 0), but no flat costs 0."""
        value = self._positive(self.estimatedValue)
        per_m2 = self._positive(self.estimatedPricePerSqm)
        estimated = value is not None and per_m2 is not None
        return Valuation(
            subject=subject,
            estimated_value=value if estimated else None,
            price_per_m2=per_m2 if estimated else None,
            radius_m=self._metres(self.radiusKm),
            radius_ceiling_m=self._ceiling(self.radiusCeilingM),
            period_months=self._rounded(self.periodMonths),
            stats=None if self.stats is None else self.stats.to_model(),
            comparables=tuple(item.to_model() for item in self.transactions),
        )

    @classmethod
    def _ceiling(cls, metres: int | float | str | None) -> int | None:
        """``radiusCeilingM`` in whole metres; one that rounds to 0 m or less is none."""
        # [W] the meaning: the widest radius the service widens its comparable transactions
        # to, read from the name and from Cisna, where radiusKm 1 reached it with only 2
        # transactions. The field itself is in the response (docs/discovery/endpoints.md,
        # "5. Valuation"), 1000 in every capture [P 2026-10-09 api.standalone_val,
        # page.offer_report; P 2026-10-15 tests/fixtures/api/standalone_val_cisna_20261015.json].
        found = cls._rounded(metres)
        return found if found is not None and found > 0 else None

    @classmethod
    def _metres(cls, kilometres: int | float | str | None) -> int | None:
        """``radiusKm`` 0.2 -> 200 m."""
        value = cls._number(kilometres)
        return None if value is None else round(value * 1000)
