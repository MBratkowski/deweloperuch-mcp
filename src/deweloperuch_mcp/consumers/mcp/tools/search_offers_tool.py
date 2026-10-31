"""``SearchOffersTool`` (D17 reference): offers in a city or in one of its districts."""

from typing import Annotated

from mcp.types import CallToolResult
from pydantic import Field

from deweloperuch_mcp.consumers.mcp.presenters.search_offers_mcp_presenter import (
    OffersResult,
    SearchOffersMcpPresenter,
)
from deweloperuch_mcp.consumers.mcp.support.calls import SessionContext, run, session_of
from deweloperuch_mcp.consumers.mcp.support.inputs import (
    Area,
    McpPerPage,
    OptionalChoice,
    OptionalWholeNumber,
    Page,
    Price,
    PricePerM2,
    null_is,
    whole_or,
)
from deweloperuch_mcp.consumers.mcp.support.tool_base import ToolBase
from deweloperuch_mcp.consumers.shared.choices import SortChoice, StatusChoice
from deweloperuch_mcp.models.values import DEFAULT_PAGE_SIZE
from deweloperuch_mcp.usecases.search_offers import SearchOffersRequest


class SearchOffersTool(ToolBase):
    # pages-rsc.md: the list of a city or of one of its districts, internal pages of the
    # site (D21) [P 2026-10-31]; the district comes as its name, as search_locations gives
    # it, and becomes the service's slug [W] (``OffersQuery``). [P 2026-10-31] the three
    # ranges up to an end, the price below the first one (not the last change), archived
    # offers, the dearest first; [P 2026-10-10] offers have no rooms or floor
    # (filterRooms/filterFloors do nothing on this list). [W] on 2.0, each checked by the
    # live suite: the open ends of a range, a page of 50, the other orders, every parameter
    # on a district's list (T73), active and archived together (T72). The whole country is
    # refused: the service's list of Poland is a list of cities [P 2026-10-29].
    name = "search_offers"
    title = "Szukaj ofert mieszkań"
    description = """\
Wyszukuje oferty mieszkań od deweloperów (tylko rynek pierwotny, ceny ofertowe, nie \
transakcyjne) w jednym mieście albo w jego dzielnicy; city=polska nie działa. city_slug \
i nazwę dzielnicy daje search_locations. Filtry: cena, metraż, cena za m², dzielnica, \
status (aktywne, archiwalne) i obniżka od pierwszej ceny; sortowanie po cenie, cenie za \
m², metrażu albo największej obniżce; lista ofert nie filtruje po pokojach ani piętrze, \
ani po deweloperze (jego inwestycje daje get_developer).

Zwraca jedną stronę: total (wszystkie pasujące), returned, page, per_page, \
pages_available, truncated, hint, list_url i items (offer_id, investment_slug, \
investment_url, name, cena w PLN, metraż w m², cena za m², status, inwestycja z \
dzielnicą, deweloper z developer_slug, zmiany ceny w procentach). Pozycje są skrócone; \
szczegóły oferty i historię ceny daje get_offer. Linki podawaj użytkownikowi.

Ograniczenia: można przejrzeć najwyżej 20 stron po per_page ofert. Gdy truncated=true, \
zawęź filtry (np. dzielnica, cena) zamiast przeglądać kolejne strony. Wszystkie oferty \
jednej inwestycji daje get_investment, ceny całego miasta get_market_statistics."""

    async def __call__(
        self,
        city: Annotated[
            str,
            Field(
                title="Miasto",
                description=(
                    "city_slug jednego miasta z search_locations, np. warszawa, krakow (nie "
                    "polska: serwis nie ma listy ofert całego kraju)."
                ),
            ),
        ],
        ctx: SessionContext,
        price_min: Annotated[
            Price | None,
            OptionalWholeNumber,
            Field(title="Cena od", description="Najniższa cena oferty w PLN."),
        ] = None,
        price_max: Annotated[
            Price | None,
            OptionalWholeNumber,
            Field(title="Cena do", description="Najwyższa cena oferty w PLN."),
        ] = None,
        area_min: Annotated[
            Area | None,
            OptionalWholeNumber,
            Field(title="Metraż od", description="Najmniejszy metraż w m²."),
        ] = None,
        area_max: Annotated[
            Area | None,
            OptionalWholeNumber,
            Field(title="Metraż do", description="Największy metraż w m²."),
        ] = None,
        price_per_m2_min: Annotated[
            PricePerM2 | None,
            OptionalWholeNumber,
            Field(title="Cena za m² od", description="Najniższa cena za m² w PLN."),
        ] = None,
        price_per_m2_max: Annotated[
            PricePerM2 | None,
            OptionalWholeNumber,
            Field(title="Cena za m² do", description="Najwyższa cena za m² w PLN."),
        ] = None,
        district: Annotated[
            str | None,
            OptionalChoice,
            Field(
                title="Dzielnica",
                description=(
                    "Nazwa dzielnicy dokładnie tak, jak podaje ją search_locations (kind=district, "
                    "pole name), np. Mokotów, Praga-Południe; razem z city_slug miasta tej "
                    "dzielnicy."
                ),
            ),
        ] = None,
        price_dropped: Annotated[
            bool,
            null_is(False),
            Field(
                title="Tylko przecenione",
                description=(
                    "true: tylko oferty, których obecna cena jest niższa od pierwszej ceny "
                    "(liczy się zmiana od pierwszej ceny, nie ostatnia zmiana)."
                ),
            ),
        ] = False,
        status: Annotated[
            StatusChoice | None,
            OptionalChoice,
            Field(
                title="Status ofert",
                description=(
                    "active (domyślnie): oferty obecnie w cennikach; archived: tylko wycofane; "
                    "all: aktywne i wycofane (total przy all może być większy niż suma active "
                    "i archived: serwis liczy je niejasno)."
                ),
            ),
        ] = "active",
        sort: Annotated[
            SortChoice | None,
            OptionalChoice,
            Field(
                title="Kolejność",
                description=(
                    "price_asc: od najtańszych, price_desc: od najdroższych, price_per_m2_asc i "
                    "price_per_m2_desc: po cenie za m², area_asc i area_desc: po metrażu, "
                    "biggest_drop: najpierw największa obniżka od pierwszej ceny (w %); brak: "
                    "domyślna kolejność serwisu (nie jest gwarantowana; zwykle najstarsze "
                    "oferty, grupami po inwestycji; to nie ranking), więc do przeglądu miasta "
                    "podaj sort."
                ),
            ),
        ] = None,
        page: Annotated[
            Page,
            whole_or(1),
            Field(
                title="Strona",
                description=(
                    "Numer strony wyników, 1–20 (dalej serwis nie udostępnia: zawęź filtry)."
                ),
            ),
        ] = 1,
        per_page: Annotated[
            McpPerPage,
            whole_or(DEFAULT_PAGE_SIZE),
            Field(
                title="Ofert na stronie",
                description=(
                    "10 albo 50. Pozycja to ok. 500 znaków wyniku (z linkiem), więc 50 daje ok. "
                    "25 tys.; zwykle wystarcza 10."
                ),
            ),
        ] = 10,
    ) -> Annotated[CallToolResult, OffersResult]:
        session = session_of(ctx)

        def search() -> OffersResult:
            request = SearchOffersRequest.parse(
                city=city,
                price_min=price_min,
                price_max=price_max,
                area_min=area_min,
                area_max=area_max,
                price_per_m2_min=price_per_m2_min,
                price_per_m2_max=price_per_m2_max,
                district=district,
                price_dropped=price_dropped,
                status=status,
                sort=sort,
                page=page,
                per_page=per_page,
            )
            return SearchOffersMcpPresenter().present(session.search_offers.execute(request))

        return await run(search)
