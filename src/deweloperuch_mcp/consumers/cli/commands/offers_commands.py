"""``deweloperuch offers search`` and ``offers get`` (D17 reference): each command parses
its request and executes the use case in a session (``call``: a package error ends the
run with its code), then hands the result to its presenter."""

from typing import Annotated

import typer

from deweloperuch_mcp.bootstrap import Session
from deweloperuch_mcp.consumers.cli.presenters.get_offer_cli_presenter import GetOfferCliPresenter
from deweloperuch_mcp.consumers.cli.presenters.search_offers_cli_presenter import (
    SearchOffersCliPresenter,
)
from deweloperuch_mcp.consumers.cli.support.common import JsonFlag, call
from deweloperuch_mcp.consumers.shared.choices import (
    DEFAULT_PAGE_SIZE,
    PageSizeChoice,
    SortChoice,
    StatusChoice,
)
from deweloperuch_mcp.usecases.get_offer import GetOfferRequest, GetOfferResult
from deweloperuch_mcp.usecases.search_offers import SearchOffersRequest, SearchOffersResult

offers_app = typer.Typer(help="Oferty mieszkań od deweloperów.", no_args_is_help=True)


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
    price_per_m2_min: Annotated[
        int | None, typer.Option("--price-per-m2-min", help="Najniższa cena za m² w PLN.")
    ] = None,
    price_per_m2_max: Annotated[
        int | None, typer.Option("--price-per-m2-max", help="Najwyższa cena za m² w PLN.")
    ] = None,
    district: Annotated[
        str | None,
        typer.Option(help="Dzielnica miasta jak w `locations search` (np. Mokotów); nie z polska."),
    ] = None,
    price_dropped: Annotated[
        bool,
        typer.Option("--price-dropped", help="Tylko oferty tańsze niż ich pierwsza cena."),
    ] = False,
    status: Annotated[
        StatusChoice | None,
        typer.Option(help="active (domyślnie), archived (wycofane) albo all (obie)."),
    ] = None,
    sort: Annotated[
        SortChoice | None,
        typer.Option(
            help=(
                "Kolejność: po cenie, cenie za m², metrażu albo najpierw największa obniżka "
                "od pierwszej ceny; bez opcji domyślna kolejność serwisu."
            )
        ),
    ] = None,
    page: Annotated[int, typer.Option(help="Numer strony, 1–20.")] = 1,
    per_page: Annotated[
        PageSizeChoice, typer.Option("--per-page", help="Liczba ofert na stronie.")
    ] = DEFAULT_PAGE_SIZE,
    as_json: JsonFlag = False,
) -> None:
    """Szukaj ofert mieszkań w mieście; najwyżej 20 stron wyników."""

    def search(session: Session) -> SearchOffersResult:
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
        return session.search_offers.execute(request)

    result = call(ctx, search)
    SearchOffersCliPresenter(as_json=as_json).present(result)


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

    def get(session: Session) -> GetOfferResult:
        request = GetOfferRequest.parse(offer_id=offer_id, investment_slug=investment)
        return session.get_offer.execute(request)

    result = call(ctx, get)
    GetOfferCliPresenter(as_json=as_json).present(result)
