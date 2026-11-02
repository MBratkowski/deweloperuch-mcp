"""``RankLocationsTool``: cities or powiats ranked by their RCN transactions, or cities by
an official indicator."""

from typing import Annotated, Any

from mcp.types import CallToolResult
from pydantic import BeforeValidator, Field

from deweloperuch_mcp.consumers.mcp.presenters.rank_locations_mcp_presenter import (
    LocationRankingResult,
    RankLocationsMcpPresenter,
)
from deweloperuch_mcp.consumers.mcp.support.calls import SessionContext, run, session_of
from deweloperuch_mcp.consumers.mcp.support.inputs import (
    OptionalChoice,
    OptionalWholeNumber,
    whole_or,
)
from deweloperuch_mcp.consumers.mcp.support.tool_base import ToolBase
from deweloperuch_mcp.consumers.shared.ranking_views import (
    IndicatorChoice,
    RankingLevelChoice,
    RankingMarketChoice,
    RankingSortChoice,
)
from deweloperuch_mcp.models.location_ranking import (
    DEFAULT_RANKING_LIMIT,
    RANKING_LIMIT_MAX,
    TRANSACTIONS_MAX,
)
from deweloperuch_mcp.usecases.rank_locations import RankLocationsRequest

Limit = Annotated[int, Field(ge=1, le=RANKING_LIMIT_MAX)]
Least = Annotated[int, Field(ge=0, le=TRANSACTIONS_MAX)]


def _choice_or(default: str) -> BeforeValidator:
    """A choice: ``null`` and ``""`` mean ``default``, spaces around it are ignored (D11)."""

    def parse(value: Any) -> Any:
        if value is None:
            return default
        if isinstance(value, str):
            return value.strip() or default
        return value

    return BeforeValidator(parse)


class RankLocationsTool(ToolBase):
    # [P 2026-11-01] statystyki/powiat-map-stats: every powiat's figures cover the 12 months
    # of periodStart..periodEndMonth, so a powiat ranking names its period; whether its
    # prices are medians or means is open (T85), as for the cities (T10), whose period the
    # service does not give: said once here, not in the fields. Counts of cities and
    # powiats come from different windows: "nie porównuj". `all` is the service's own
    # figure for both markets, not the sum of the other two (equal in 80 of 303 powiats,
    # T86): the description never calls it a sum.
    # Indicators [P 2026-11-02, tests/contract/api/dto/test_gov_map_stats_dto.py]: each
    # value equals the series of get_government_statistics for its period (unemployment of
    # the month, wages and natural increase of the year, the NBP secondary transaction price
    # of the quarter) or the sum of its 12 months (dwellings); the area matches no series,
    # so it is "podana przez serwis".
    # powiat_id: no tool takes it and search_locations has no powiats (its kinds are city,
    # district, street [P]), so the description says it is only informative.
    # [W] the default threshold of the price orders (20, PRICE_ORDER_MIN_TRANSACTIONS in
    # models/location_ranking.py): a price from a handful of transactions is chance.
    name = "rank_locations"
    title = "Ranking miast i powiatów"
    description = """\
Porównanie wielu miejsc w jednym okresie; nie zwraca szeregu czasowego. Dwa tryby: (1) bez \
indicator: ranking miejscowości (level=city) albo powiatów (level=powiat) wg transakcji z \
RCN (liczba, cena za m²); (2) z indicator: ranking 66 miast na prawach powiatu wg \
wskaźnika GUS lub NBP. Trend jednego miasta w czasie: get_transaction_statistics (RCN) \
albo get_government_statistics (GUS, NBP). Bez indicator to ceny transakcyjne z RCN, nie \
ofertowe; nbp_price_per_m2 to oficjalna cena NBP, nie RCN.

Zwraca total, returned, truncated, hint i items. Transakcje: min_transactions (zastosowany \
próg), items (name, city_slug albo powiat_id, transaction_count, price_per_m2, area_m2, \
price); dla city ranking_url (link dla użytkownika); dla powiat market i okres 12 miesięcy \
period_start–period_end. Wskaźnik: indicator, unit, period, items (name, city_slug, value, \
stats_url: link dla użytkownika).

Ograniczenia: serwis nie mówi, czy ceny i metraż to średnie, czy mediany. Okresu \
miejscowości serwis nie podaje; nie porównuj liczb transakcji miejscowości i powiatów. \
Sortowanie po cenie domyślnie pomija miejsca poniżej 20 transakcji (cena bywa \
przypadkowa); min_transactions=0 pokazuje wszystkie."""

    async def __call__(
        self,
        ctx: SessionContext,
        # [W] "także małe miasteczka i wsie": the service ranks 2448 places (api.city_tx_stats
        # [P 2026-10-09]), more than Poland has towns (about 1000); none of the 3 kept in the
        # sample is small (tests/contract/api/dto/test_city_transactions_list_dto.py pins
        # the count).
        level: Annotated[
            RankingLevelChoice,
            _choice_or("city"),
            Field(
                title="Poziom",
                description=(
                    "city: miejscowości (miasta, także małe miasteczka i wsie), domyślnie; "
                    "powiat: powiaty, tylko transakcje (market); powiaty nie mają city_slug "
                    "ani ranking_url i nie ma ich w search_locations. Z indicator tylko city."
                ),
            ),
        ] = "city",
        sort: Annotated[
            RankingSortChoice | None,
            OptionalChoice,
            Field(
                title="Kolejność",
                description=(
                    "transactions_desc: najwięcej transakcji (domyślnie bez indicator); "
                    "price_per_m2_desc, price_per_m2_asc: najwyższa, najniższa cena za m² "
                    "(miejsca bez ceny na końcu); value_desc (domyślnie z indicator), "
                    "value_asc: najwyższa, najniższa wartość wskaźnika, tylko z indicator."
                ),
            ),
        ] = None,
        limit: Annotated[
            Limit,
            whole_or(DEFAULT_RANKING_LIMIT),
            Field(
                title="Liczba pozycji",
                description=(
                    "Ile pierwszych pozycji rankingu zwrócić, 1–100, domyślnie 20. Pozycja to "
                    "ok. 120 znaków wyniku. Dla pełnych list zawężaj min_transactions, nie "
                    "podnoś limitu bez potrzeby."
                ),
            ),
        ] = DEFAULT_RANKING_LIMIT,
        min_transactions: Annotated[
            Least | None,
            OptionalWholeNumber,
            Field(
                title="Najmniej transakcji",
                description=(
                    "Brak = próg domyślny: 20 przy sortowaniu po cenie, 0 przy "
                    "transactions_desc. 0 = wszystkie miejsca. Pomija miejsca z mniejszą "
                    "liczbą transakcji; np. 50 daje stabilniejsze ceny. Nie działa z "
                    "indicator."
                ),
            ),
        ] = None,
        market: Annotated[
            RankingMarketChoice | None,
            OptionalChoice,
            Field(
                title="Rynek",
                description=(
                    "Tylko level=powiat. secondary: rynek wtórny (domyślnie); primary: "
                    "pierwotny; all: oba rynki w zestawieniu serwisu (jego liczba transakcji "
                    "nie zawsze równa się secondary + primary). Powiaty bez danych dla rynku "
                    "są pominięte (hint)."
                ),
            ),
        ] = None,
        indicator: Annotated[
            IndicatorChoice | None,
            OptionalChoice,
            Field(
                title="Wskaźnik",
                description=(
                    "Ranking 66 miast na prawach powiatu według wskaźnika zamiast transakcji "
                    "(bez level=powiat, min_transactions i market): unemployment_rate: stopa "
                    "bezrobocia rejestrowanego (%) w miesiącu; average_wage: przeciętne "
                    "miesięczne wynagrodzenie brutto (PLN), średnia za rok period (jak "
                    "dataset=wages w get_government_statistics); dwellings_completed, "
                    "dwellings_started: mieszkania oddane, rozpoczęte w 12 miesiącach do "
                    "miesiąca period; average_dwelling_area: powierzchnia mieszkania (m²) "
                    "podana przez serwis za okres period; nie porównuj jej z average_area z "
                    "get_government_statistics (inna definicja); natural_increase: przyrost "
                    "naturalny (osoby) w roku; nbp_price_per_m2: cena transakcyjna rynku "
                    "wtórnego wg NBP (PLN/m²) w kwartale, tylko 17 miast. Miasta bez wartości "
                    "są pominięte (hint)."
                ),
            ),
        ] = None,
    ) -> Annotated[CallToolResult, LocationRankingResult]:
        session = session_of(ctx)

        def rank() -> LocationRankingResult:
            request = RankLocationsRequest.parse(
                level=level,
                sort=sort,
                limit=limit,
                min_transactions=min_transactions,
                market=market,
                indicator=indicator,
            )
            return RankLocationsMcpPresenter().present(session.rank_locations.execute(request))

        return await run(rank)
