"""``GetTransactionStatisticsTool``: RCN transaction prices of flats in a city over time."""

from typing import Annotated

from mcp.types import CallToolResult
from pydantic import Field

from deweloperuch_mcp.consumers.mcp.presenters.get_transaction_statistics_mcp_presenter import (
    MAX_PERIODS,
    GetTransactionStatisticsMcpPresenter,
    TransactionStatisticsResult,
)
from deweloperuch_mcp.consumers.mcp.support.calls import SessionContext, run, session_of
from deweloperuch_mcp.consumers.mcp.support.inputs import OptionalChoice, null_is, whole_or
from deweloperuch_mcp.consumers.mcp.support.tool_base import ToolBase
from deweloperuch_mcp.consumers.shared.choices import DEFAULT_GRANULARITY, GranularityChoice
from deweloperuch_mcp.models.government_statistics import DEFAULT_PERIODS
from deweloperuch_mcp.usecases.get_transaction_statistics import GetTransactionStatisticsRequest

Periods = Annotated[int, Field(ge=1, le=MAX_PERIODS)]


class GetTransactionStatisticsTool(ToolBase):
    # Facts below: [P] docs/discovery/endpoints.md, section 4 (samples api.monthly_tx and
    # api.avg_trend_city): monthly medians and averages since 2021, a quarterly average
    # price of one m² since 2017, the latest months with few transactions (RCN lag).
    # [W] "mediana"/"średnia": read from the field names (api/dto/monthly_transaction_stats_dto.py).
    # [W] "kilkumiesięcznym": models.transaction_series.Granularity.lag_note. Only flats and
    # city slugs are [P]: no houses, districts, streets, counties, nor polska. [P 2026-10-13]
    # live: a month without transactions (Warsaw 2026-05/06) has no prices (the service sends
    # zeros). [W] incomplete and last_complete_period: the rules above
    # models.transaction_series.INCOMPLETE_SHARE and MIN_USUAL_TRANSACTIONS (the revision
    # horizon is open, T46).
    name = "get_transaction_statistics"
    title = "Ceny transakcyjne w czasie"
    description = """\
Zwraca ceny transakcyjne mieszkań w mieście z Rejestru Cen Nieruchomości (RCN) w \
kolejnych miesiącach albo kwartałach: liczbę transakcji i ceny za m². To ceny \
faktycznych sprzedaży, a nie ceny ofertowe deweloperów (search_offers, \
get_market_statistics) ani oficjalne ceny NBP (get_government_statistics).

granularity=month (domyślnie): mediana i średnia ceny za m², mediana metrażu i mediana \
ceny mieszkania. granularity=quarter: tylko średnia cena za m² i liczba transakcji, za \
to dłuższa historia. Miesiące i kwartały to różne statystyki: nie łącz ich w jeden \
wykres ani szereg.

Zwraca periods (od najstarszego; okres bez transakcji nie ma cen) oraz total, \
returned, truncated, available_from, last_complete_period, hint, note i stats_url \
(link).

Ograniczenia: tylko mieszkania i całe miasta (city_slug z search_locations; bez \
dzielnic, ulic i całej Polski). Domyślnie ostatnie 12 okresów; truncated=true znaczy, \
że są starsze (zwiększ periods, najwyżej 60). Najnowsze okresy są niepełne \
(opóźnienie RCN). Okres z incomplete=true pomiń: nie podawaj jego cen jako trendu. \
Trend kończ na last_complete_period (jego dane też mogą się zmienić); brak pola (za \
mało transakcji): czytaj hint."""

    async def __call__(
        self,
        city: Annotated[
            str,
            Field(
                title="Miasto",
                description=(
                    "city_slug miasta z search_locations, np. warszawa, krakow, gdansk (małe "
                    "litery bez polskich znaków). Statystyki są dla całych miast; dzielnice, "
                    "ulice i cała Polska (polska) nie są obsługiwane."
                ),
            ),
        ],
        ctx: SessionContext,
        granularity: Annotated[
            GranularityChoice,
            null_is(DEFAULT_GRANULARITY),
            OptionalChoice,
            Field(
                title="Długość okresu",
                description=(
                    "month (domyślnie): miesiące, z medianą i średnią ceny za m², medianą "
                    "metrażu i medianą ceny mieszkania; quarter: kwartały, tylko średnia cena "
                    "za m² i liczba transakcji, ale dłuższa historia."
                ),
            ),
        ] = DEFAULT_GRANULARITY,
        periods: Annotated[
            Periods,
            whole_or(DEFAULT_PERIODS),
            Field(
                title="Liczba okresów",
                description=(
                    "Ile ostatnich okresów (miesięcy albo kwartałów) zwrócić, 1–60, domyślnie "
                    "12. 60 miesięcy to ok. 9 tys. znaków; dla trendu wieloletniego wybierz "
                    "quarter zamiast wielu miesięcy."
                ),
            ),
        ] = DEFAULT_PERIODS,
    ) -> Annotated[CallToolResult, TransactionStatisticsResult]:
        session = session_of(ctx)

        def get() -> TransactionStatisticsResult:
            request = GetTransactionStatisticsRequest.parse(
                city=city, granularity=granularity, periods=periods
            )
            return GetTransactionStatisticsMcpPresenter().present(
                session.get_transaction_statistics.execute(request)
            )

        return await run(get)
