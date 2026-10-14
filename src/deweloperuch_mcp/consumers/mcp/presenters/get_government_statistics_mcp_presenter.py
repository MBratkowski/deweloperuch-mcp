"""``GetGovernmentStatisticsMcpPresenter``: ``get_government_statistics``'s result for a
model and its output schema (``GovernmentStatisticsResult``): the series as a table, one
list of periods and the values of each series aligned with it (``null`` inside a list is
a period without data and stays)."""

from pydantic import Field

from deweloperuch_mcp.consumers.mcp.support.mcp_model import McpModel
from deweloperuch_mcp.consumers.shared.government_statistics_views import (
    GovernmentStatisticsView,
)
from deweloperuch_mcp.usecases.get_government_statistics import GetGovernmentStatisticsResult

STATS_URL = "Link do sekcji z tymi danymi w serwisie: podaj go użytkownikowi."
STATS_HINT = "Co zrobić dalej, gdy wynik jest obcięty."

# Class docstrings would become schema descriptions for the model: comments instead.


class SeriesItem(McpModel):
    series_id: str = Field(description="Stały identyfikator szeregu, np. completed_total.")
    label: str
    unit: str = Field(description="mieszkania, m², osoby, %, PLN albo PLN/m².")
    values: list[int | float | None] = Field(
        description="Wartości kolejnych okresów z periods (ta sama długość); null = brak danych."
    )


class GovernmentStatisticsResult(McpModel):
    # The series as a table: one list of periods, the values of each series aligned with
    # it (the domain keeps a point per period; this is shorter for a model).
    location_slug: str
    location_name: str
    dataset: str
    title: str
    source: str = Field(description="Źródło danych: GUS, NBP albo Eurostat.")
    frequency: str = Field(description="year (lata), quarter (kwartały) albo month (miesiące).")
    total: int = Field(description="Wszystkie okresy, które serwis ma dla tego zestawu.")
    returned: int = Field(description="Okresy w wyniku: ostatnie z nich.")
    truncated: bool = Field(
        description="true: są starsze okresy niż pokazane; co dalej, mówi hint."
    )
    available_from: str = Field(description="Najstarszy okres, jaki ma serwis.")
    hint: str | None = Field(None, description=STATS_HINT)
    note: str | None = Field(
        None, description="Uwaga do danych, np. ostatni kwartał obejmuje tylko część miesięcy."
    )
    stats_url: str | None = Field(None, description=STATS_URL)
    periods: list[str] = Field(
        description="Okresy od najstarszego: 2025 (rok), 2025-Q3 (kwartał) albo 2025-08 (miesiąc)."
    )
    series: list[SeriesItem]


class GetGovernmentStatisticsMcpPresenter:
    """The statistics as their view has them (``GovernmentStatisticsView``), as a table:
    ``periods`` and each series' ``values`` in that order.

    A truncated result gets its own hint: the tool returns at most ``max_periods``
    periods, so "ask for more" is offered only below that cap.
    """

    def __init__(self, *, max_periods: int) -> None:
        self._max_periods = max_periods

    def present(self, result: GetGovernmentStatisticsResult) -> GovernmentStatisticsResult:
        view = GovernmentStatisticsView.from_result(result)
        return GovernmentStatisticsResult(
            location_slug=view.location_slug,
            location_name=view.location_name,
            dataset=view.dataset.value,
            title=view.title,
            source=view.source,
            frequency=view.frequency.value,
            total=view.total,
            returned=view.returned,
            truncated=view.truncated,
            available_from=view.available_from,
            hint=self._hint(view),
            note=view.note,
            stats_url=view.stats_url,
            periods=list(view.periods),
            series=[
                SeriesItem(
                    series_id=series.series_id,
                    label=series.label,
                    unit=series.unit.value,
                    values=[self._compact(point.value) for point in series.points],
                )
                for series in view.series
            ],
        )

    def _hint(self, view: GovernmentStatisticsView) -> str | None:
        """What to do about older periods: a larger ``periods`` up to ``max_periods``; at
        the cap, nothing (one call returns no more). Not truncated: the use case's hint."""
        if not view.truncated:
            return view.hint
        shown = (
            f"Pokazano ostatnie {view.returned} z {view.total} okresów (dane od "
            f"{view.available_from})"
        )
        if view.returned >= self._max_periods:
            return (
                f"{shown}. To maksimum w jednym wywołaniu; starszych okresów tym narzędziem nie "
                "pobierzesz."
            )
        return f"{shown}; starsze pokaże większe periods (najwyżej {self._max_periods})."

    @staticmethod
    def _compact(value: float | None) -> int | float | None:
        """``3611.0`` -> ``3611``: whole values without ``.0`` (shorter for a model)."""
        return int(value) if value is not None and value.is_integer() else value
