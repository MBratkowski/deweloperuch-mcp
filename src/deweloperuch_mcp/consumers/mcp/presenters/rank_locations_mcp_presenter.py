"""``RankLocationsMcpPresenter``: ``rank_locations``' result for a model (the view's names,
D3) and its output schema (``LocationRankingResult``)."""

from pydantic import Field

from deweloperuch_mcp.consumers.mcp.support.mcp_model import McpModel
from deweloperuch_mcp.consumers.shared.ranking_views import LocationRankingView
from deweloperuch_mcp.usecases.rank_locations import RankLocationsResult

# [W] the same slugs as search_locations: Kraków is krakow in both samples
# (api.city_tx_stats, api.cities_q) [P]; for every place it is a conclusion.
CITY_SLUG = "Slug miejscowości (level=city), w tym samym formacie co city_slug z search_locations."

# Class docstrings would become schema descriptions for the model: comments instead.


class RankedLocationItem(McpModel):
    name: str = Field(description="Nazwa miejscowości albo powiatu.")
    city_slug: str | None = Field(None, description=CITY_SLUG)
    powiat_id: int | None = Field(
        None,
        description=(
            "Identyfikator powiatu w serwisie (level=powiat), informacyjny: żadne narzędzie "
            "go nie przyjmuje."
        ),
    )
    transaction_count: int = Field(
        description=(
            "Liczba transakcji wg serwisu; okresu serwis nie podaje (dla powiatów wiele lat: "
            "tylko do uporządkowania)."
        )
    )
    price_per_m2: float | None = Field(
        None, description="Cena transakcyjna za m² w PLN, podana przez serwis."
    )
    area_m2: float | None = Field(None, description="Metraż w m², podany przez serwis.")
    price: float | None = Field(None, description="Cena transakcyjna w PLN, podana przez serwis.")


class LocationRankingResult(McpModel):
    level: str = Field(description="city (miejscowości) albo powiat (powiaty).")
    sort: str = Field(description="Kolejność rankingu, jak w argumencie sort.")
    min_transactions: int = Field(
        description=(
            "Zastosowany próg: min_transactions z argumentu, a bez niego domyślny: 20 przy "
            "sortowaniu po cenie, 0 przy transactions_desc (0 = wszystkie miejsca)."
        )
    )
    total: int = Field(
        description="Wszystkie miejsca tego poziomu z co najmniej min_transactions transakcji."
    )
    returned: int = Field(description="Pozycje w items: pierwsze z rankingu.")
    truncated: bool = Field(
        description="true: miejsc jest więcej, niż pokazano; co dalej, mówi hint."
    )
    hint: str | None = Field(
        None,
        description=(
            "Co zrobić, gdy wynik jest obcięty albo pusty, oraz czy przy sortowaniu po cenie "
            "pominięto małe miejsca (domyślny próg)."
        ),
    )
    ranking_url: str | None = Field(
        None,
        description=(
            "Strona rankingu miast na deweloperuch.pl (tylko level=city): podaj ją "
            "użytkownikowi jako link."
        ),
    )
    items: list[RankedLocationItem]


class RankLocationsMcpPresenter:
    """The ranking as its view has it (``LocationRankingView``), described for a model."""

    def present(self, result: RankLocationsResult) -> LocationRankingResult:
        return LocationRankingResult.model_validate(
            LocationRankingView.from_result(result).model_dump()
        )
