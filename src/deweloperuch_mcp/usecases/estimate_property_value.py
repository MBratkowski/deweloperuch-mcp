"""Use case ``EstimatePropertyValue``: the value of a flat, estimated from the transactions
(RCN) around it."""

from dataclasses import dataclass
from typing import Self

from deweloperuch_mcp.models.valuation import ComparablesLimit, ValuationListing, ValuationSubject
from deweloperuch_mcp.usecases.ports import ValuationSource
from deweloperuch_mcp.usecases.support.arguments import ParameterCheck
from deweloperuch_mcp.usecases.support.failures import ReportedAs

# [H] why the service gives no estimate (docs/open-questions.md): the text names a
# possibility, not a cause. The point itself is already checked to be in Poland.
NO_ESTIMATE = "Serwis nie podał wyceny dla tego miejsca; w promieniu może nie być transakcji."
# T41: one fractional request matched a whole-area estimate; the general rule is unknown.
FRACTIONAL_AREA = "Serwis może nie uwzględnić części ułamkowej powierzchni w wycenie."

# [W] "the widest radius" is the meaning of the ceiling (models.valuation.Valuation.
# at_widest_radius), read from its name and from Cisna.
WIDEST_RADIUS = "(największego, jaki serwis bierze pod uwagę)"
NO_TRANSACTIONS = "Serwis nie podał transakcji, na których oparł wycenę"
LOW_CONFIDENCE = "to orientacyjna wartość o niskiej wiarygodności. Podaj ją z tym zastrzeżeniem"
COMPARE = "porównaj też z cenami transakcyjnymi miasta (get_transaction_statistics)."
"""The caveat of an estimate of low confidence: the facts, ``LOW_CONFIDENCE``, the spread
of prices when there is one, ``COMPARE``."""


@dataclass(frozen=True, kw_only=True)
class EstimatePropertyValueRequest:
    """What to value and how many comparable transactions to show, checked (``parse``)
    before anything is sent."""

    subject: ValuationSubject
    limit: ComparablesLimit | None = None
    """At most this many comparable transactions (``None``: all)."""

    @classmethod
    def parse(
        cls,
        *,
        lat: object,
        lng: object,
        area_m2: object,
        address: object = None,
        limit: object = None,
    ) -> Self:
        """Checked in this order: lat, lng, area_m2, address, limit. A refusal names the
        parameter (``InvalidInputError``)."""
        with ParameterCheck():
            return cls(
                subject=ValuationSubject.parse(lat, lng, area_m2, address),
                limit=ComparablesLimit.parse(limit),
            )


@dataclass(frozen=True, kw_only=True)
class EstimatePropertyValueResult:
    """The valuation with the comparable transactions a result shows, and what to do next
    (``hint``)."""

    listing: ValuationListing

    @property
    def valuation_hint(self) -> str | None:
        """Cautions about the valuation, independent of how many comparables are shown."""
        hints = []
        if not self.listing.valuation.estimated:
            hints.append(NO_ESTIMATE)
        if self.listing.valuation.subject.area.value % 1:
            hints.append(FRACTIONAL_AREA)
        return " ".join(hints) or None

    @property
    def hint(self) -> str | None:
        """The caveat of the estimate (``caveat``), guidance about comparable transactions
        left out (D4) and the valuation cautions (``valuation_hint``), in this order;
        ``None`` when none applies."""
        hints = [self.caveat()]
        if self.listing.valuation.estimated and self.listing.truncated:
            hints.append(f"{self.nearest_shown()}; więcej pokaże większy limit.")
        hints.append(self.valuation_hint)
        return " ".join(hint for hint in hints if hint) or None

    def caveat(self) -> str | None:
        """What an estimate is to be given with, naming its facts; ``None`` when nothing:

        - of low confidence (``Valuation.low_confidence``): ``Wycena oparta tylko na 2
          transakcjach z promienia 1 000 m (największego, jaki serwis bierze pod uwagę) z
          ostatnich 24 miesięcy: to orientacyjna wartość o niskiej wiarygodności. ...``;
        - from the widest radius only: ``Transakcje porównawcze pochodzą z promienia
          1 000 m (...), więc wycena opisuje szerszą okolicę i jest orientacyjna.``, no
          word of low confidence.
        """
        valuation = self.listing.valuation
        radius = valuation.radius_m
        if valuation.low_confidence:
            return self._low_confidence()
        if valuation.estimated and valuation.at_widest_radius and radius is not None:
            return (
                f"Transakcje porównawcze pochodzą z promienia {self._grouped(radius)} m "
                f"{WIDEST_RADIUS}, więc wycena opisuje szerszą okolicę i jest orientacyjna."
            )
        return None

    def _low_confidence(self) -> str:
        """The facts (how many transactions, the radius, the widest one, the months; the
        words agreeing with the numbers), ``LOW_CONFIDENCE``, the spread of their prices
        per m² and ``COMPARE``; ``NO_TRANSACTIONS`` instead of "na 0 transakcjach"."""
        valuation = self.listing.valuation
        count = valuation.counted_comparables
        if count == 0:
            return f"{NO_TRANSACTIONS}: {LOW_CONFIDENCE}; {COMPARE}"
        transactions = "transakcji" if count == 1 else "transakcjach"
        said = [f"Wycena oparta tylko na {count} {transactions}"]
        if valuation.radius_m is not None:
            said.append(f"z promienia {self._grouped(valuation.radius_m)} m")
            if valuation.at_widest_radius:
                said.append(WIDEST_RADIUS)
        if valuation.period_months == 1:
            said.append("z ostatniego miesiąca")
        elif valuation.period_months is not None:
            said.append(f"z ostatnich {valuation.period_months} miesięcy")
        return f"{' '.join(said)}: {LOW_CONFIDENCE}{self._spread()}; {COMPARE}"

    def _spread(self) -> str:
        """`` i z rozpiętością cen za m² tych transakcji (2 302–5 778 PLN/m²)`` from the
        statistics; ``""`` without a lowest and a higher highest price."""
        stats = self.listing.valuation.stats
        low = None if stats is None else stats.min_price_per_m2
        high = None if stats is None else stats.max_price_per_m2
        if low is None or high is None or low >= high:
            return ""
        prices = f"{self._grouped(low)}–{self._grouped(high)} PLN/m²"
        return f" i z rozpiętością cen za m² tych transakcji ({prices})"

    @staticmethod
    def _grouped(value: float) -> str:
        """``1000`` -> ``1 000``: whole numbers in Polish digit groups, as the CLI prints
        them next to these texts."""
        return f"{round(value):,}".replace(",", " ")

    def nearest_shown(self) -> str:
        """``Pokazano 1 najbliższą z 3 transakcji porównawczych``, the words agreeing with
        the numbers (1 najbliższą, 2–4 najbliższe, otherwise najbliższych; of 1 transakcji
        porównawczej)."""
        returned, total = self.listing.returned, self.listing.total
        if returned == 1:
            nearest = "najbliższą"
        elif returned % 10 in (2, 3, 4) and returned % 100 not in (12, 13, 14):
            nearest = "najbliższe"
        else:
            nearest = "najbliższych"
        of = "transakcji porównawczej" if total == 1 else "transakcji porównawczych"
        return f"Pokazano {returned} {nearest} z {total} {of}"


class EstimatePropertyValue:
    """One request to the service per valuation; the domain keeps the nearest comparable
    transactions, at most ``limit`` (D4), and never the service's working data (D5)."""

    def __init__(self, source: ValuationSource) -> None:
        self._source = source

    def execute(self, request: EstimatePropertyValueRequest) -> EstimatePropertyValueResult:
        with ReportedAs("Wycena mieszkania", not_found=NO_ESTIMATE):
            valuation = self._source.valuation(request.subject)
        return EstimatePropertyValueResult(listing=valuation.nearest(request.limit))
