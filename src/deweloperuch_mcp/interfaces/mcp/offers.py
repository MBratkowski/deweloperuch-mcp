"""Tools ``search_offers`` and ``get_offer``: offers in a city and one offer's history."""

from typing import Annotated

from mcp.types import CallToolResult
from pydantic import Field

from deweloperuch_mcp.application import arguments
from deweloperuch_mcp.bootstrap import Session
from deweloperuch_mcp.domain.values import DEFAULT_PAGE_SIZE, WHOLE_COUNTRY
from deweloperuch_mcp.interfaces import views
from deweloperuch_mcp.interfaces.choices import SortChoice
from deweloperuch_mcp.interfaces.mcp import presenters
from deweloperuch_mcp.interfaces.mcp.calls import SessionContext, run, session_of
from deweloperuch_mcp.interfaces.mcp.inputs import (
    Area,
    McpPerPage,
    OfferId,
    OptionalChoice,
    OptionalWholeNumber,
    Page,
    Price,
    WholeNumber,
    whole_or,
)
from deweloperuch_mcp.interfaces.mcp.presenters import OfferResult, OffersResult


def _search(session: Session, city: str, **filters: object) -> views.OfferSearchResult:
    return views.offer_search(session.search_offers(arguments.offer_search(city, **filters)))


SEARCH_OFFERS = """\
Wyszukuje oferty mieszkań od deweloperów (tylko rynek pierwotny, ceny ofertowe, nie \
transakcyjne) w jednym mieście albo w całej Polsce (city=polska), z filtrami ceny i \
metrażu i sortowaniem po cenie. Użyj, gdy szukasz mieszkań w budżecie albo o danym \
metrażu. Nie filtruje po dzielnicy, liczbie pokoi ani deweloperze.

Zwraca jedną stronę: total (wszystkie pasujące), returned, page, per_page, \
pages_available, truncated, hint, list_url i items (offer_id, investment_slug, \
investment_url (strona inwestycji, nie pojedynczej oferty), name, cena w PLN, metraż w \
m², cena za m², status, inwestycja, deweloper, ostatnia zmiana ceny i zmiana od \
pierwszej ceny w procentach; miasto tylko przy city=polska). Pozycje są skrócone; \
szczegóły oferty i historię ceny daje get_offer. list_url to link „zobacz wszystkie na \
deweloperuch.pl” z tymi samymi filtrami: przydatny, gdy truncated=true albo użytkownik \
chce więcej ofert. Linki podawaj użytkownikowi, np. w tabeli ofert.

Ograniczenia: można przejrzeć najwyżej 20 stron po per_page ofert. Gdy truncated=true, \
zawęź filtry zamiast przeglądać kolejne strony. Wszystkie oferty jednej inwestycji daje \
get_investment."""

GET_OFFER = """\
Zwraca jedną ofertę z pełną historią ceny, inwestycją i deweloperem. Użyj, gdy chcesz \
zobaczyć, jak zmieniała się cena mieszkania. Wymaga offer_id i investment_slug (oba \
podaje search_offers albo get_investment): samo offer_id nie wystarcza.

Zwraca cenę, metraż, cenę za m², status (active albo archived), zmianę od pierwszej \
ceny, daty i price_history (date, kind: offer, archived albo restored, price). \
investment_url i developer_url to strony inwestycji i dewelopera na deweloperuch.pl: \
podawaj je użytkownikowi jako linki. Do listy ofert jednej inwestycji użyj \
get_investment."""


async def search_offers(
    city: Annotated[
        str,
        Field(
            title="Miasto",
            description=(
                "city_slug miasta z search_locations (np. warszawa, krakow) albo polska "
                "dla całego kraju."
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
    sort: Annotated[
        SortChoice | None,
        OptionalChoice,
        Field(
            title="Kolejność",
            description=(
                "price_asc: od najtańszych, price_desc: od najdroższych; brak: domyślna "
                "kolejność serwisu (nie jest gwarantowana)."
            ),
        ),
    ] = None,
    page: Annotated[
        Page, whole_or(1), Field(title="Strona", description="Numer strony wyników, 1–20.")
    ] = 1,
    per_page: Annotated[
        McpPerPage,
        whole_or(DEFAULT_PAGE_SIZE),
        Field(
            title="Ofert na stronie",
            description=(
                "10 albo 50. Pozycja to ok. 450 znaków wyniku (z linkiem), więc 50 daje ok. "
                "22 tys.; "
                "zwykle wystarcza 10."
            ),
        ),
    ] = 10,
) -> Annotated[CallToolResult, OffersResult]:
    session = session_of(ctx)
    return await run(
        lambda: presenters.offers(
            _search(
                session,
                city,
                price_min=price_min,
                price_max=price_max,
                area_min=area_min,
                area_max=area_max,
                sort=sort,
                page=page,
                per_page=per_page,
            ),
            whole_country=city.strip() == WHOLE_COUNTRY,
        )
    )


async def get_offer(
    offer_id: Annotated[
        OfferId,
        WholeNumber,
        Field(title="Oferta", description="offer_id z search_offers albo get_investment."),
    ],
    investment_slug: Annotated[
        str,
        Field(
            title="Inwestycja",
            description="investment_slug inwestycji tej oferty, np. smolna (z search_offers).",
        ),
    ],
    ctx: SessionContext,
) -> Annotated[CallToolResult, OfferResult]:
    session = session_of(ctx)
    return await run(
        lambda: presenters.offer(
            views.offer_detail(session.get_offer(*arguments.offer(offer_id, investment_slug)))
        )
    )
