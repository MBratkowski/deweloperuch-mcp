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
    # Facts below, from two internal channels of the site (D21,
    # api/adapters/transaction_statistics_api.py):
    # - months [P 2026-10-31]: the statistics page of a city (docs/discovery/pages-rsc.md,
    #   `transakcje`; tests/fixtures/rsc/stats_tx_*_20261031.rsc): one row a month since
    #   2017-01, to the newest month with transactions (the page's empty months after it are
    #   dropped), flats of the secondary market only. The adapter refuses a month with other
    #   transactions with its own message (api/dto/transaction_stats_page_dto.py,
    #   OTHER_MARKET), so "tylko rynek wtórny" holds for every city it answers. [W]
    #   "mediana"/"średnia": the field names.
    # - quarters: docs/discovery/endpoints.md, avg-price-trend/city: since 2017-Q1 [P]; the
    #   price of one m² is a median [P 2026-10-30] (api/dto/city_trend_dto.py); no mean,
    #   area or price of a flat. Their market is open (T45): "rynek nieokreślony". 60 of them
    #   cover the whole history, 60 months only 5 years (MAX_PERIODS).
    # - [P 2026-10-13, P 2026-10-31] the latest months have few transactions (RCN lag), and a
    #   month without transactions has no prices (the service sends zeros). [W] incomplete and
    #   last_complete_period: the rules above models.transaction_series.INCOMPLETE_SHARE and
    #   MIN_USUAL_TRANSACTIONS (the revision horizon is open, T46).
    # - Only flats and city slugs: no houses (T75), districts, streets, counties, aggregates
    #   (models.transaction_series.TransactionCity.AGGREGATES) nor polska.
    name = "get_transaction_statistics"
    title = "Ceny transakcyjne w czasie"
    description = """\
Zwraca ceny transakcyjne mieszkań w mieście z Rejestru Cen Nieruchomości (RCN) od 2017 \
r., w kolejnych miesiącach albo kwartałach: liczbę transakcji i ceny za m². To ceny \
faktycznych sprzedaży, a nie ceny ofertowe deweloperów (search_offers, \
get_market_statistics) ani oficjalne ceny NBP (get_government_statistics).

granularity=month (domyślnie): tylko rynek wtórny; mediana i średnia ceny za m², \
mediana metrażu i mediana ceny mieszkania. granularity=quarter: tylko mediana ceny za \
m² i liczba transakcji; rynek nieokreślony. Miesiące i kwartały to różne statystyki: \
nie łącz ich w jeden wykres ani szereg.

Ograniczenia: tylko mieszkania i całe miasta (city_slug z search_locations; bez \
dzielnic, ulic, agregatów (np. 7-miast) i całej Polski). Domyślnie ostatnie 12 okresów; \
truncated=true znaczy, że są starsze (zwiększ periods, najwyżej 60; całą historię od \
2017 r. daje tylko quarter). Dane RCN spływają z opóźnieniem, więc najnowsze okresy są \
niepełne: okres z incomplete=true pomiń, nie podawaj jego cen jako trendu. Okres bez \
transakcji nie ma cen. Trend kończ na last_complete_period (jego dane też mogą się \
zmienić); brak pola (za mało transakcji): czytaj hint."""

    async def __call__(
        self,
        city: Annotated[
            str,
            Field(
                title="Miasto",
                description=(
                    "city_slug miasta z search_locations, np. warszawa, krakow, gdansk (małe "
                    "litery bez polskich znaków). Statystyki są dla całych miast; dzielnice, "
                    "ulice, agregaty miast (np. 7-miast) i cała Polska (polska) nie są "
                    "obsługiwane."
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
                    "month (domyślnie): miesiące, tylko rynek wtórny, z medianą i średnią ceny "
                    "za m², medianą metrażu i medianą ceny mieszkania; quarter: kwartały, tylko "
                    "mediana ceny za m² i liczba transakcji (rynek nieokreślony), za to cała "
                    "historia od 2017 r. w jednym wywołaniu (periods=60)."
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
