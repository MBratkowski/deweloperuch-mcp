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
    def hint(self) -> str | None:
        """What to do about a valuation without an estimate, or about comparable
        transactions left out (D4); ``None`` otherwise."""
        if not self.listing.valuation.estimated:
            return NO_ESTIMATE
        if self.listing.truncated:
            return f"{self.nearest_shown()}; więcej pokaże większy limit."
        return None

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
