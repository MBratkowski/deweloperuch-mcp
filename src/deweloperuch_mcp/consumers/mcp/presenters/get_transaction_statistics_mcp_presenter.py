"""``GetTransactionStatisticsMcpPresenter``: ``get_transaction_statistics``' result for a
model, compact (a list of periods, no ``null`` fields: the quarterly data has no medians),
and its output schema (``TransactionStatisticsResult``)."""

from typing import Annotated

from pydantic import Field, PlainSerializer

from deweloperuch_mcp.consumers.mcp.support.mcp_model import McpModel
from deweloperuch_mcp.consumers.shared.transaction_views import TransactionStatisticsView
from deweloperuch_mcp.models.transaction_series import Granularity
from deweloperuch_mcp.usecases.get_transaction_statistics import GetTransactionStatisticsResult

MAX_PERIODS = 60
"""Periods one call may return: 5 years of months, about 9k characters (a month is
about 140); the service has 67 months and 39 quarters [P 2026-10-09], so a longer
trend is one call with quarters (about 75 characters each)."""


def _compact(value: float | None) -> int | float | None:
    """``10651.0`` -> ``10651``: whole values without ``.0`` (shorter for a model)."""
    return int(value) if value is not None and value.is_integer() else value


Value = Annotated[float | None, PlainSerializer(_compact)]
"""A price or an area: ``number`` in the schema, whole values written without ``.0``."""

STATS_URL = (
    "Strona statystyk transakcji na deweloperuch.pl dla ludzi: podaj ją użytkownikowi jako link."
)

# Class docstrings would become schema descriptions for the model: comments instead.


class TransactionPeriodItem(McpModel):
    period: str = Field(description="Miesiąc (2025-08) albo kwartał (2025-Q3).")
    transactions: int = Field(
        description="Liczba transakcji w okresie (w najnowszych okresach zaniżona, zob. note)."
    )
    incomplete: bool | None = Field(
        None,
        description=(
            "true: okres ma mniej niż połowę zwykłej liczby transakcji, bo dane RCN są "
            "jeszcze niepełne; nie wyciągaj wniosków z jego cen ani liczby transakcji. Pole "
            "jest tylko przy takich okresach."
        ),
    )
    median_price_per_m2: Value = Field(
        None, description="Mediana ceny transakcyjnej 1 m² w PLN (tylko month)."
    )
    average_price_per_m2: Value = Field(None, description="Średnia cena transakcyjna 1 m² w PLN.")
    median_area_m2: Value = Field(None, description="Mediana metrażu w m² (tylko month).")
    median_price: Value = Field(
        None, description="Mediana ceny transakcyjnej mieszkania w PLN (tylko month)."
    )


class TransactionStatisticsResult(McpModel):
    city_slug: str
    granularity: str = Field(description="month (miesiące) albo quarter (kwartały).")
    total: int = Field(description="Wszystkie okresy, które serwis ma dla miasta.")
    returned: int = Field(description="Okresy w wyniku: ostatnie z nich.")
    truncated: bool = Field(
        description="true: są starsze okresy niż pokazane; co dalej, mówi hint."
    )
    available_from: str = Field(description="Najstarszy okres, jaki ma serwis.")
    last_complete_period: str | None = Field(
        None,
        description=(
            "Najnowszy okres ze zwykłą liczbą transakcji (nie incomplete), pokazany lub nie; "
            "na nim kończ trend, choć jego dane mogą się jeszcze zmienić. Brak pola: za "
            "krótka historia albo za mało transakcji, by to ocenić."
        ),
    )
    hint: str | None = Field(
        None,
        description=(
            "Co zrobić dalej: gdy wynik jest obcięty, ma okresy incomplete albo za mało "
            "transakcji, by je ocenić."
        ),
    )
    note: str = Field(description="Uwaga do danych: najnowsze okresy są niepełne.")
    stats_url: str | None = Field(None, description=STATS_URL)
    periods: list[TransactionPeriodItem] = Field(
        description="Okresy od najstarszego; okres bez transakcji nie ma cen ani metrażu."
    )


class GetTransactionStatisticsMcpPresenter:
    """The periods with the measures a model needs: the averages of area and price stay
    in the CLI's ``--json``; ``incomplete`` only where it is true. A truncated result gets
    its own hint (``_hint``)."""

    def present(self, result: GetTransactionStatisticsResult) -> TransactionStatisticsResult:
        data = TransactionStatisticsView.from_result(result).model_dump(mode="json")
        data["hint"] = self._hint(result)
        for item in data["periods"]:
            item["incomplete"] = item["incomplete"] or None
        return TransactionStatisticsResult.model_validate(data)

    @staticmethod
    def _hint(result: GetTransactionStatisticsResult) -> str | None:
        """What to do about older periods: a larger ``periods`` up to ``MAX_PERIODS``; at
        the cap, nothing (one call returns no more); then the use case's word on the
        newest periods. Not truncated: the use case's hint."""
        statistics = result.statistics
        if not statistics.truncated:
            return result.hint
        shown = (
            f"Pokazano ostatnie {statistics.returned} z {statistics.total} okresów (dane od "
            f"{statistics.available_from})"
        )
        if statistics.returned >= MAX_PERIODS:
            longer = "; dłuższy trend pokaże granularity=quarter"
            if statistics.granularity is not Granularity.MONTH:
                longer = ""
            older = f"{shown}. To maksimum w jednym wywołaniu{longer}."
        else:
            older = f"{shown}; starsze pokaże większe periods (najwyżej {MAX_PERIODS})."
        return " ".join(part for part in (older, result.latest_periods_hint) if part)
