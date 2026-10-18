"""``RankLocationsTool``: cities or powiats ranked by their RCN transactions."""

from typing import Annotated, Any

from mcp.types import CallToolResult
from pydantic import BeforeValidator, Field

from deweloperuch_mcp.consumers.mcp.presenters.rank_locations_mcp_presenter import (
    LocationRankingResult,
    RankLocationsMcpPresenter,
)
from deweloperuch_mcp.consumers.mcp.support.calls import SessionContext, run, session_of
from deweloperuch_mcp.consumers.mcp.support.inputs import OptionalWholeNumber, whole_or
from deweloperuch_mcp.consumers.mcp.support.tool_base import ToolBase
from deweloperuch_mcp.consumers.shared.ranking_views import RankingLevelChoice, RankingSortChoice
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
    # [P] api.city_tx_stats and api.powiat_stats (2026-10-09): Warszawa has 3606 transactions
    # as a city and 351314 as a powiat (the same area: a city with powiat rights), while its
    # months have about 1.0-1.3k (api.monthly_tx). [W] the powiat counts span many years and
    # the city counts about a quarter
    # (tests/contract/api/dto/test_powiat_transactions_list_dto.py): hence "wiele lat" and
    # "tylko do uporządkowania"; the period itself stays unknown (T10).
    # [H] T10: whether avg_* are averages or medians (said once here, not in the fields), and
    # the period and base of *_change: no changes over time at all.
    # powiat_id: no tool takes it and search_locations has no powiats (its kinds are city,
    # district, street [P]), so the description says it is only informative.
    # [W] the default threshold of the price orders (20, PRICE_ORDER_MIN_TRANSACTIONS in
    # models/location_ranking.py): a price from a handful of transactions is chance.
    name = "rank_locations"
    title = "Ranking miast i powiatów"
    description = """\
Ranking miejscowości (level=city) albo powiatów (level=powiat) w Polsce według \
transakcji z Rejestru Cen Nieruchomości (RCN): liczba transakcji i cena transakcyjna za \
m². Dla porównania wielu miast: to narzędzie; dla trendu jednego miasta w czasie: \
get_transaction_statistics. To ceny transakcyjne, nie ofertowe; oferty deweloperów daje \
search_offers.

Zwraca min_transactions (zastosowany próg), total (miejsca z co najmniej tyloma \
transakcjami), returned, truncated, hint i items (name, city_slug albo powiat_id, \
transaction_count, price_per_m2, area_m2, price); dla city także ranking_url (strona \
rankingu na deweloperuch.pl: podaj ją użytkownikowi jako link). powiat_id jest \
informacyjny: żadne narzędzie go nie przyjmuje.

Ograniczenia: serwis nie podaje okresu ani tego, czy ceny i metraż to średnie, czy \
mediany: przedstawiaj je jako wartości podane przez serwis. Liczby transakcji powiatów \
obejmują wiele lat: służą tylko do uporządkowania, nie są bieżącym wolumenem; nie \
porównuj ich z liczbami miejscowości. Sortowanie po cenie domyślnie pomija miejsca \
poniżej 20 transakcji (cena bywa przypadkowa); min_transactions=0 pokazuje wszystkie, \
np. 50 daje stabilniejsze ceny."""

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
                    "powiat: powiaty (bez ranking_url i bez odpowiednika w search_locations)."
                ),
            ),
        ] = "city",
        sort: Annotated[
            RankingSortChoice,
            _choice_or("transactions_desc"),
            Field(
                title="Kolejność",
                description=(
                    "transactions_desc: najwięcej transakcji (domyślnie); price_per_m2_desc: "
                    "najwyższa cena za m²; price_per_m2_asc: najniższa cena za m². Miejsca "
                    "bez ceny są na końcu."
                ),
            ),
        ] = "transactions_desc",
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
                    "liczbą transakcji; np. 50 daje stabilniejsze ceny."
                ),
            ),
        ] = None,
    ) -> Annotated[CallToolResult, LocationRankingResult]:
        session = session_of(ctx)

        def rank() -> LocationRankingResult:
            request = RankLocationsRequest.parse(
                level=level, sort=sort, limit=limit, min_transactions=min_transactions
            )
            return RankLocationsMcpPresenter().present(session.rank_locations.execute(request))

        return await run(rank)
