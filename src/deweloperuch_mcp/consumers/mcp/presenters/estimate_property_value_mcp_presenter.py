"""``EstimatePropertyValueMcpPresenter``: ``estimate_property_value``'s result for a model,
and its output schema (``ValuationResult``).

The valuation without the service's working data (D5): the estimate and whether it is of
low confidence, the radius and period of the comparable transactions, statistics of their
prices per m² and the nearest of them that the use case kept (D4: total, returned,
omitted, truncated).
"""

import datetime as dt

from pydantic import Field

from deweloperuch_mcp.consumers.mcp.support.mcp_model import McpModel
from deweloperuch_mcp.consumers.shared.valuation_views import ValuationView
from deweloperuch_mcp.usecases.estimate_property_value import EstimatePropertyValueResult

# --- the result (class docstrings would become schema descriptions: comments instead) ----

AREA = "Metraż w m²."


class ComparableItem(McpModel):
    # One comparable transaction; the register's ids of units and buildings stay out.
    address: str | None = Field(None, description="Ulica i numer budynku.")
    date: dt.date | None = Field(None, description="Data transakcji.")
    price: float | None = Field(None, description="Cena transakcyjna w PLN (nie ofertowa).")
    area_m2: float | None = Field(None, description=AREA)
    price_per_m2: float | None = Field(None, description="Cena transakcyjna za m² w PLN.")
    floor: int | None = Field(None, description="Piętro.")
    # [P] the service rounds to the nearest 50 m (api.dto.standalone_valuation_dto).
    distance_m: float | None = Field(
        None, description="Przybliżona odległość od wycenianego punktu w m (do 50 m)."
    )
    market: str | None = Field(
        None, description="primary (rynek pierwotny) albo secondary (rynek wtórny)."
    )
    building_slug: str | None = Field(
        None, description="Identyfikator budynku: building_slug dla get_building."
    )


class PriceStatsItem(McpModel):
    # [W] the service's own figures; count equals the comparable transactions in both
    # samples, but whether transactions it excludes count is not known.
    count: int | None = Field(None, description="Liczba transakcji wg serwisu.")
    median_price_per_m2: float | None = Field(None, description="Mediana ceny za m² w PLN.")
    average_price_per_m2: float | None = Field(None, description="Średnia cena za m² w PLN.")
    min_price_per_m2: float | None = Field(None, description="Najniższa cena za m² w PLN.")
    max_price_per_m2: float | None = Field(None, description="Najwyższa cena za m² w PLN.")


class ValuationResult(McpModel):
    keep_null = frozenset({"estimated_value"})  # always there: null means no estimate

    lat: float
    lng: float
    area_m2: float = Field(description="Metraż podany w zapytaniu w m².")
    estimated_value: float | None = Field(
        description=(
            "Szacowana wartość mieszkania w PLN podana przez serwis: przybliżenie, nie "
            "operat szacunkowy. null: serwis nie podał wyceny."
        )
    )
    # Like truncated, false is shown: an estimate always says whether it is reliable.
    low_confidence: bool | None = Field(
        None,
        description=(
            "true: wycena o niskiej wiarygodności (mniej niż 5 transakcji porównawczych); "
            "hint mówi, na czym się opiera. Podaj ją tylko jako orientacyjną, z zastrzeżeniem z "
            "hint. Jest przy każdej wycenie, brak przy estimated_value=null."
        ),
    )
    price_per_m2: float | None = Field(None, description="Szacowana cena za m² w PLN.")
    radius_m: int | None = Field(
        None, description="Promień w metrach, z którego są transakcje porównawcze."
    )
    period_months: int | None = Field(
        None, description="Z ilu ostatnich miesięcy są transakcje porównawcze."
    )
    stats: PriceStatsItem | None = Field(
        None, description="Statystyki cen za m² podane przez serwis."
    )
    comparables_total: int = Field(description="Wszystkie transakcje porównawcze serwisu.")
    comparables_returned: int = Field(description="Transakcji na liście comparables.")
    comparables_omitted: int = Field(description="Transakcji pominiętych przez limit.")
    truncated: bool = Field(
        description="true: lista comparables jest niepełna (comparables_omitted > 0)."
    )
    hint: str | None = Field(None, description="Co zrobić dalej.")
    comparables: list[ComparableItem] = Field(
        description="Transakcje porównawcze od najbliższych, najwyżej limit."
    )


class EstimatePropertyValueMcpPresenter:
    """The valuation as its view has it (``ValuationView``) without the address the caller
    gave, with the D4 counters and a hint of its own when the list is cut: one call
    returns at most ``max_comparables`` comparable transactions."""

    def __init__(self, *, max_comparables: int) -> None:
        self._max_comparables = max_comparables

    def present(self, result: EstimatePropertyValueResult) -> ValuationResult:
        view = ValuationView.from_result(result)
        data = view.model_dump()
        data["comparables_returned"] = len(view.comparables)
        data["truncated"] = view.comparables_omitted > 0
        data["hint"] = self._hint(result)
        return ValuationResult.model_validate(data)

    def _hint(self, result: EstimatePropertyValueResult) -> str | None:
        """More comparable transactions: a larger ``limit`` up to ``max_comparables``; at the
        cap, nothing (one call returns no more); between the caveat of the estimate and the
        valuation cautions, as in the use case's hint. Otherwise the use case's hint."""
        listing = result.listing
        if listing.omitted <= 0:
            return result.hint
        shown = result.nearest_shown()
        if listing.returned >= self._max_comparables:
            guidance = (
                f"{shown}. To maksimum w jednym wywołaniu; stats to statystyki podane przez serwis."
            )
        else:
            guidance = f"{shown}; więcej pokaże większy limit (najwyżej {self._max_comparables})."
        hints = (result.caveat(), guidance, result.valuation_hint)
        return " ".join(hint for hint in hints if hint)
