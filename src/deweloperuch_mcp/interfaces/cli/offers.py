"""``deweloperuch offers search`` and ``offers get``: offers and one offer's history."""

from typing import Annotated

import typer

from deweloperuch_mcp.application import arguments
from deweloperuch_mcp.bootstrap import Session
from deweloperuch_mcp.interfaces import views
from deweloperuch_mcp.interfaces.choices import DEFAULT_PAGE_SIZE, PageSizeChoice, SortChoice
from deweloperuch_mcp.interfaces.cli.common import JsonFlag, call, show
from deweloperuch_mcp.interfaces.cli.text import format_offer, format_offer_search

offers_app = typer.Typer(help="Oferty mieszkań od deweloperów.", no_args_is_help=True)


def _search(session: Session, city: str, **filters: object) -> views.OfferSearchResult:
    return views.offer_search(session.search_offers(arguments.offer_search(city, **filters)))


@offers_app.command("search")
def offers_search(
    ctx: typer.Context,
    city: Annotated[
        str,
        typer.Argument(
            metavar="CITY",
            help="Slug miasta (np. warszawa; podaje go `locations search`) albo polska.",
        ),
    ],
    price_min: Annotated[
        int | None, typer.Option("--price-min", help="Najniższa cena w PLN.")
    ] = None,
    price_max: Annotated[
        int | None, typer.Option("--price-max", help="Najwyższa cena w PLN.")
    ] = None,
    area_min: Annotated[
        int | None, typer.Option("--area-min", help="Najmniejszy metraż w m².")
    ] = None,
    area_max: Annotated[
        int | None, typer.Option("--area-max", help="Największy metraż w m².")
    ] = None,
    sort: Annotated[
        SortChoice | None,
        typer.Option(help="Kolejność po cenie; bez opcji domyślna kolejność serwisu."),
    ] = None,
    page: Annotated[int, typer.Option(help="Numer strony, 1–20.")] = 1,
    per_page: Annotated[
        PageSizeChoice, typer.Option("--per-page", help="Liczba ofert na stronie.")
    ] = DEFAULT_PAGE_SIZE,
    as_json: JsonFlag = False,
) -> None:
    """Szukaj ofert mieszkań w mieście; najwyżej 20 stron wyników."""
    result = call(
        ctx,
        lambda session: _search(
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
    )
    show(result, as_json, format_offer_search)


@offers_app.command("get")
def offers_get(
    ctx: typer.Context,
    offer_id: Annotated[
        int, typer.Argument(metavar="OFFER_ID", help="Identyfikator oferty z `offers search`.")
    ],
    investment: Annotated[
        str,
        typer.Option(
            "--investment",
            metavar="SLUG",
            help="Slug inwestycji oferty (investment_slug z `offers search`).",
        ),
    ],
    as_json: JsonFlag = False,
) -> None:
    """Pokaż ofertę z historią ceny."""
    result = call(
        ctx,
        lambda session: views.offer_detail(
            session.get_offer(*arguments.offer(offer_id, investment))
        ),
    )
    show(result, as_json, format_offer)
