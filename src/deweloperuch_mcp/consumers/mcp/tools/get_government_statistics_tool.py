"""``GetGovernmentStatisticsTool``: GUS and NBP time series of a location."""

from typing import Annotated

from mcp.types import CallToolResult
from pydantic import Field

from deweloperuch_mcp.consumers.mcp.presenters.get_government_statistics_mcp_presenter import (
    GetGovernmentStatisticsMcpPresenter,
    GovernmentStatisticsResult,
)
from deweloperuch_mcp.consumers.mcp.support.calls import SessionContext, run, session_of
from deweloperuch_mcp.consumers.mcp.support.inputs import Choice, whole_or
from deweloperuch_mcp.consumers.mcp.support.tool_base import ToolBase
from deweloperuch_mcp.consumers.shared.choices import DatasetChoice
from deweloperuch_mcp.models.government_statistics import DEFAULT_PERIODS
from deweloperuch_mcp.usecases.get_government_statistics import GetGovernmentStatisticsRequest

MAX_PERIODS = 120
"""Periods ``get_government_statistics`` may return: 10 years of months, about 10.5k
characters for the widest dataset (dwellings of polska, 15 series); the default 12 gives
at most about 3k."""
Periods = Annotated[int, Field(ge=1, le=MAX_PERIODS)]


class GetGovernmentStatisticsTool(ToolBase):
    # Facts below are [P 2026-10-11] (tests/fixtures/rsc/stats_gov_*.rsc): the page's list of
    # 69 locations (3 aggregates, 66 cities, NBP prices for 17 of them and the aggregates),
    # polska without its own NBP series, the last quarter of dwellings holding 2 of 3 months,
    # the latest data of 2026-10-11 being months (2026-08) and quarters (NBP 2026-Q2) old.
    # [W] demography and wages: monthly for polska, yearly for warszawa [P]; "dla miast
    # rocznie" generalizes warszawa to every city, so the description points to `frequency`.
    # Whether search_locations gives the same city slugs is not confirmed (jastrzebie is not
    # the name's slug), so the location description does not tie them together.
    name = "get_government_statistics"
    title = "Statystyki GUS i NBP"
    description = """\
Zwraca oficjalne statystyki GUS i NBP jako szeregi czasowe dla Polski, agregatu miast \
albo miasta na prawach powiatu: mieszkania oddane do użytkowania i rozpoczęte (razem, \
wg form budownictwa, na wynajem), średnią powierzchnię mieszkań oddanych przez \
deweloperów, średnie ceny m² wg NBP (rynek pierwotny i wtórny, ceny ofertowe i \
transakcyjne), stopę bezrobocia, wynagrodzenia, demografię i ludność. Użyj jako \
kontekstu rynku; ofert i cen konkretnych mieszkań tu nie ma (search_offers).

Zwraca periods (od najstarszego) i series (series_id, label, unit, values wyrównane z \
periods; null = brak danych) oraz frequency, source, total, returned, truncated, \
available_from, note i stats_url (sekcja strony na deweloperuch.pl: podaj ją \
użytkownikowi jako link).

Ograniczenia: domyślnie ostatnie 12 okresów; truncated=true znaczy, że są starsze \
(zwiększ periods, najwyżej 120). nbp_prices: tylko 17 dużych miast i 3 agregaty, nie \
polska. Nie każdy zestaw jest dostępny dla każdej lokalizacji (błąd wskaże, co podać); \
dane GUS i NBP są publikowane z opóźnieniem, ostatni okres bywa sprzed kilku tygodni lub \
miesięcy. Przeczytaj note: ostatni okres bywa niepełny."""

    async def __call__(
        self,
        location: Annotated[
            str,
            Field(
                title="Lokalizacja",
                description=(
                    "polska (cała Polska), agregat 7-miast, 10-miast albo 6-miast-bez-warszawy, "
                    "albo jedno z 66 miast na prawach powiatu: nazwa małymi literami bez polskich "
                    "znaków, z myślnikami zamiast spacji, np. warszawa, krakow, lodz, "
                    "bielsko-biala, zielona-gora; Jastrzębie-Zdrój to jastrzebie. Dane są tylko "
                    "dla 66 miast na prawach powiatu, a nie dla dzielnic i mniejszych "
                    "miejscowości."
                ),
            ),
        ],
        dataset: Annotated[
            DatasetChoice,
            Choice,
            Field(
                title="Zestaw danych",
                description=(
                    "dwellings_quarterly: mieszkania oddane do użytkowania i rozpoczęte (razem, "
                    "wg form budownictwa, na wynajem), kwartalnie; dwellings_monthly: to samo "
                    "miesięcznie; average_area: średnia powierzchnia mieszkania oddanego przez "
                    "deweloperów (m², rocznie); demography: urodzenia żywe, zgony, przyrost "
                    "naturalny (dla Polski miesięcznie, dla miast rocznie); population: ludność, "
                    "kobiety i mężczyźni (rocznie); "
                    "unemployment: stopa bezrobocia rejestrowanego (%, miesięcznie); wages: "
                    "przeciętne miesięczne wynagrodzenie brutto w PLN (dla Polski miesięcznie, "
                    "dla miast rocznie, czasem z relacją do średniej krajowej); nbp_prices: "
                    "średnie ceny m² wg NBP, rynek pierwotny i wtórny, ofertowe i transakcyjne "
                    "(PLN/m², kwartalnie). Częstotliwość zwraca pole frequency."
                ),
            ),
        ],
        ctx: SessionContext,
        periods: Annotated[
            Periods,
            whole_or(DEFAULT_PERIODS),
            Field(
                title="Liczba okresów",
                description=(
                    "Ile ostatnich okresów zwrócić (lat, kwartałów albo miesięcy), 1–120, "
                    "domyślnie 12. Najszerszy zestaw (mieszkania, 15 szeregów) przy 120 "
                    "miesiącach to ok. 10 tys. znaków. Dla trendów bierz dane roczne/kwartalne; "
                    "miesięczne 120 okresów tylko, gdy użytkownik o to prosi."
                ),
            ),
        ] = DEFAULT_PERIODS,
    ) -> Annotated[CallToolResult, GovernmentStatisticsResult]:
        session = session_of(ctx)

        def get() -> GovernmentStatisticsResult:
            request = GetGovernmentStatisticsRequest.parse(
                location=location, dataset=dataset, periods=periods
            )
            presenter = GetGovernmentStatisticsMcpPresenter(max_periods=MAX_PERIODS)
            return presenter.present(session.get_government_statistics.execute(request))

        return await run(get)
