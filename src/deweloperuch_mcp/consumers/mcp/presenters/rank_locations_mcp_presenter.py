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
    transaction_count: int | None = Field(
        None,
        description=(
            "Liczba transakcji wg serwisu: dla powiatu w okresie period_start–period_end, "
            "dla miejscowości w okresie, którego serwis nie podaje."
        ),
    )
    price_per_m2: float | None = Field(
        None, description="Cena transakcyjna za m² w PLN, podana przez serwis."
    )
    area_m2: float | None = Field(None, description="Metraż w m², podany przez serwis.")
    price: float | None = Field(None, description="Cena transakcyjna w PLN, podana przez serwis.")
    value: float | None = Field(
        None, description="Wartość wskaźnika (indicator) w jednostce unit za okres period."
    )
    stats_url: str | None = Field(
        None,
        description=(
            "Link do strony wskaźnika miasta na deweloperuch.pl (tylko z indicator): podaj "
            "go użytkownikowi."
        ),
    )


class LocationRankingResult(McpModel):
    level: str = Field(description="city (miejscowości) albo powiat (powiaty).")
    sort: str = Field(description="Kolejność rankingu, jak w argumencie sort.")
    min_transactions: int | None = Field(
        None,
        description=(
            "Zastosowany próg: min_transactions z argumentu, a bez niego domyślny: 20 przy "
            "sortowaniu po cenie, 0 przy transactions_desc (0 = wszystkie miejsca). Brak "
            "przy indicator."
        ),
    )
    market: str | None = Field(
        None, description="Rynek rankingu powiatów: secondary, primary albo all."
    )
    period_start: str | None = Field(
        None, description="Pierwszy dzień okresu transakcji powiatów (RRRR-MM-01)."
    )
    period_end: str | None = Field(
        None,
        description="Ostatni miesiąc okresu transakcji powiatów (RRRR-MM), wliczony w okres.",
    )
    indicator: str | None = Field(None, description="Wskaźnik rankingu, jak w argumencie.")
    unit: str | None = Field(
        None,
        description=(
            "Jednostka value: %, PLN/mies., mieszkania (suma 12 miesięcy), m², osoby albo PLN/m²."
        ),
    )
    period: str | None = Field(
        None,
        description=(
            "Okres wartości wskaźnika: miesiąc (RRRR-MM), kwartał (RRRR-Qn) albo rok (RRRR); "
            "dla dwellings_completed i dwellings_started ostatni miesiąc okna 12 miesięcy."
        ),
    )
    total: int = Field(
        description=(
            "Wszystkie miejsca spełniające kryteria: z co najmniej min_transactions "
            "transakcji, z danymi dla market albo z wartością wskaźnika."
        )
    )
    returned: int = Field(description="Pozycje w items: pierwsze z rankingu.")
    truncated: bool = Field(
        description="true: miejsc jest więcej, niż pokazano; co dalej, mówi hint."
    )
    hint: str | None = Field(
        None,
        description=(
            "Co zrobić, gdy wynik jest obcięty albo pusty, oraz co pominięto: małe miejsca "
            "przy sortowaniu po cenie (domyślny próg), powiaty bez danych dla market, miasta "
            "bez wskaźnika."
        ),
    )
    ranking_url: str | None = Field(
        None,
        description=(
            "Strona rankingu miast na deweloperuch.pl (tylko level=city bez indicator): "
            "podaj ją użytkownikowi jako link."
        ),
    )
    items: list[RankedLocationItem]


class RankLocationsMcpPresenter:
    """The ranking as its view has it (``LocationRankingView``), described for a model."""

    def present(self, result: RankLocationsResult) -> LocationRankingResult:
        return LocationRankingResult.model_validate(
            LocationRankingView.from_result(result).model_dump()
        )
