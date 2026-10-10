"""``deweloperuch``: the command line over the domain services (D6)::

    deweloperuch locations search QUERY [--json]
    deweloperuch offers search CITY [--price-min N] [--price-max N] [--area-min N]
        [--area-max N] [--sort price_asc|price_desc] [--page N] [--per-page 10|50|100] [--json]
    deweloperuch offers get OFFER_ID --investment SLUG [--json]
    deweloperuch investments get SLUG [--history] [--limit N] [--json]

A thin layer: typer checks types and enums, the services check everything else (their
messages say what to fix). Each run opens one ``services.Session`` and closes it. Text
for people by default (Polish); ``--json`` prints the domain model. Errors of the package
go to stderr without a traceback and end the run with the codes of ``ExitCode``.

Imports only ``services``, ``errors`` and ``domain.models`` from the package, never the
client (D6; tests/test_layering.py).
"""

from collections.abc import Callable
from enum import IntEnum
from typing import Annotated, TypeVar

import typer
from pydantic import BaseModel

from deweloperuch_mcp import services
from deweloperuch_mcp.domain.models import (
    Investment,
    Location,
    LocationSearchResult,
    OfferBase,
    OfferDetail,
    OfferSearchResult,
    PriceEvent,
)
from deweloperuch_mcp.errors import (
    DeweloperuchError,
    InvalidInputError,
    LimiterWaitError,
    NotFoundError,
    ServiceBlockedError,
    ServiceError,
    UnexpectedResponseError,
)


class ExitCode(IntEnum):
    """Exit codes of ``deweloperuch`` (public API)."""

    OK = 0
    UNEXPECTED = 1
    """Any other error, e.g. ``SessionClosedError`` or a bug (with a traceback)."""
    INVALID_INPUT = 2
    """``InvalidInputError``, and wrong types or enum values (typer's usage errors)."""
    STOP = 3
    """``ServiceBlockedError`` and ``RateLimitedError``: stop and tell the user."""
    SERVICE_ERROR = 4
    LIMITER_WAIT = 5
    UNEXPECTED_RESPONSE = 6
    NOT_FOUND = 7


# Subclasses before their bases: UnexpectedResponseError is a ServiceError.
_EXIT_CODES: tuple[tuple[type[DeweloperuchError], ExitCode], ...] = (
    (InvalidInputError, ExitCode.INVALID_INPUT),
    (ServiceBlockedError, ExitCode.STOP),
    (UnexpectedResponseError, ExitCode.UNEXPECTED_RESPONSE),
    (ServiceError, ExitCode.SERVICE_ERROR),
    (LimiterWaitError, ExitCode.LIMITER_WAIT),
    (NotFoundError, ExitCode.NOT_FOUND),
)


# The STOP latch lasts only as long as the process: a shell loop would go on sending.
STOP_ADVICE = (
    "Nie uruchamiaj kolejnych poleceń deweloperuch ani pętli: przerwij i zgłoś to. "
    "Przy 429 odczekaj co najmniej czas podany wyżej."
)


def exit_code(error: DeweloperuchError) -> ExitCode:
    return next(
        (code for kind, code in _EXIT_CODES if isinstance(error, kind)), ExitCode.UNEXPECTED
    )


app = typer.Typer(
    name="deweloperuch",
    help=(
        "Ceny ofertowe mieszkań od deweloperów (rynek pierwotny) z deweloperuch.pl. "
        "Tylko odczyt; zapytania idą przez wspólny limiter (najwyżej 1 na sekundę)."
    ),
    no_args_is_help=True,
    add_completion=False,
    pretty_exceptions_show_locals=False,
)
locations_app = typer.Typer(help="Lokalizacje: miasta, dzielnice, ulice.", no_args_is_help=True)
offers_app = typer.Typer(help="Oferty mieszkań od deweloperów.", no_args_is_help=True)
investments_app = typer.Typer(help="Inwestycje deweloperskie.", no_args_is_help=True)
app.add_typer(locations_app, name="locations")
app.add_typer(offers_app, name="offers")
app.add_typer(investments_app, name="investments")


def main() -> None:
    """Entry point of the ``deweloperuch`` script."""
    app()


JsonFlag = Annotated[bool, typer.Option("--json", help="Wypisz wynik jako JSON (model domenowy).")]
R = TypeVar("R", bound=BaseModel)


def _call(ctx: typer.Context, service: Callable[[services.Session], R]) -> R:
    """Run ``service`` in a new session; a package error ends the run with its code.

    ``ctx.obj`` may be a session factory (tests pass one with a fast limiter).
    """
    open_session: Callable[[], services.Session] = (
        ctx.obj if callable(ctx.obj) else services.Session
    )
    try:
        with open_session() as session:
            return service(session)
    except DeweloperuchError as err:
        code = exit_code(err)
        typer.echo(f"Błąd: {err}", err=True)
        if err.detail:
            typer.echo(f"Szczegóły: {err.detail}", err=True)
        if code is ExitCode.STOP:
            typer.echo(STOP_ADVICE, err=True)
        raise typer.Exit(code) from None


def _print(result: R, as_json: bool, text: Callable[[R], str]) -> None:
    typer.echo(result.model_dump_json(indent=2) if as_json else text(result))


# --- commands ------------------------------------------------------------------------------


@locations_app.command("search")
def locations_search(
    ctx: typer.Context,
    query: Annotated[
        str,
        typer.Argument(
            metavar="QUERY",
            help="Fragment nazwy miasta, dzielnicy lub ulicy (2–100 znaków), np. krak.",
        ),
    ],
    as_json: JsonFlag = False,
) -> None:
    """Znajdź miasta, dzielnice i ulice; podaje slug miasta do `offers search`."""
    result = _call(ctx, lambda session: services.search_locations(session, query))
    _print(result, as_json, format_locations)


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
        services.OfferSort | None,
        typer.Option(help="Kolejność po cenie; bez opcji domyślna kolejność serwisu."),
    ] = None,
    page: Annotated[int, typer.Option(help="Numer strony, 1–20.")] = 1,
    per_page: Annotated[
        services.PerPage, typer.Option("--per-page", help="Liczba ofert na stronie.")
    ] = services.DEFAULT_PER_PAGE,
    as_json: JsonFlag = False,
) -> None:
    """Szukaj ofert mieszkań w mieście; najwyżej 20 stron wyników."""
    result = _call(
        ctx,
        lambda session: services.search_offers(
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
    _print(result, as_json, format_offer_search)


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
    result = _call(ctx, lambda session: services.get_offer(session, offer_id, investment))
    _print(result, as_json, format_offer)


@investments_app.command("get")
def investments_get(
    ctx: typer.Context,
    slug: Annotated[
        str,
        typer.Argument(metavar="SLUG", help="Slug inwestycji (investment_slug z `offers search`)."),
    ],
    history: Annotated[
        bool, typer.Option("--history", help="Dołącz historię ceny każdej oferty (wolniej).")
    ] = False,
    limit: Annotated[
        int | None,
        typer.Option(help="Najwięcej pokazanych ofert (najpierw aktywne); domyślnie wszystkie."),
    ] = None,
    as_json: JsonFlag = False,
) -> None:
    """Pokaż inwestycję z deweloperem i ofertami."""
    result = _call(
        ctx,
        lambda session: services.get_investment(
            session, slug, include_history=history, limit=limit
        ),
    )
    _print(result, as_json, format_investment)


# --- text output ---------------------------------------------------------------------------

_KINDS = {"city": "miasto", "district": "dzielnica", "street": "ulica"}
_STATUSES = {"active": "aktywna", "archived": "archiwalna"}
_EVENTS = {"offer": "cena", "archived": "wycofanie", "restored": "przywrócenie"}


def format_locations(result: LocationSearchResult) -> str:
    if result.total is None:
        head = f"Lokalizacje: pokazano {result.returned}, może być więcej."
    else:
        head = f"Lokalizacje: {result.total}."
    lines = [head, *(_location_line(item) for item in result.items)]
    if result.hint:
        lines.append(f"Wskazówka: {result.hint}")
    if result.items:
        lines.append("W nawiasach [] slug miasta dla: deweloperuch offers search CITY_SLUG")
    return "\n".join(lines)


def _location_line(item: Location) -> str:
    name = item.name if item.name == item.city else f"{item.name}, {item.city}"
    line = f"{_KINDS.get(item.kind, item.kind):<9}  {name} [{item.city_slug}]"
    if item.offer_count is not None:
        # [W] docs/discovery/endpoints.md, location-search: `count` of districts and streets
        # is the number of offers; hence "ok." for them.
        about = "" if item.kind == "city" else "ok. "
        line += f" · ofert: {about}{_number(item.offer_count)}"
    return line


def format_offer_search(result: OfferSearchResult) -> str:
    head = [f"Pasujące oferty: {_number(result.total)}"]
    if result.pages_available:
        head.append(f"strona {result.page} z {result.pages_available} (po {result.per_page})")
    head.append(f"pokazano {result.returned}")
    if result.truncated:
        head.append(f"obcięte: serwis pozwala przejrzeć najwyżej {services.MAX_PAGES} stron")
    lines = [" · ".join(head) + "."]
    if result.hint:
        lines.append(f"Wskazówka: {result.hint}")
    for item in result.items:
        lines.append(_offer_line(item))
        where = f"    {item.investment_name} [{item.investment_slug}] · {item.developer_name}"
        lines.append(where + (f" · {item.city}" if item.city else ""))
    if result.items:
        lines.append(
            "Szczegóły oferty: deweloperuch offers get OFFER_ID --investment INVESTMENT_SLUG"
        )
    return "\n".join(lines)


def format_offer(offer: OfferDetail) -> str:
    unit = offer.currency or ""
    lines = [
        f"[{offer.offer_id}] {offer.name} · {_status(offer.status)}",
        "Cena: " + " · ".join(_measures(offer)),
    ]
    if offer.price_change_since_start is not None:
        lines.append(f"Od pierwszej ceny: {_change(offer)}")
    lines += [
        f"Inwestycja: {offer.investment_name} [{offer.investment_slug}] · {offer.city}",
        f"Deweloper: {offer.developer.name} [{offer.developer.developer_slug}]",
    ]
    dates = [
        f"{label} {value.isoformat()}"
        for label, value in (
            ("dodana", offer.creation_date),
            ("ostatnie zdarzenie", offer.last_event_date),
            ("ostatnia zmiana", offer.last_change_date),
        )
        if value is not None
    ]
    if dates:
        lines.append("Daty: " + " · ".join(dates))
    lines.append(f"Historia ceny ({len(offer.price_history)}):")
    lines += [_event_line(event, unit) for event in offer.price_history]
    return "\n".join(lines)


def format_investment(investment: Investment) -> str:
    unit = investment.currency or ""
    place = f"Miejsce: {investment.city} [{investment.city_slug}]"
    if investment.street:
        place += f", {investment.street}"
    if investment.lat is not None and investment.lng is not None:
        place += f" · {investment.lat:.5f}, {investment.lng:.5f}"
    averages = [
        _amount(investment.avg_price, unit),
        _amount(investment.avg_area_m2, "m²", 2),
        _amount(investment.avg_price_per_m2, _per_m2(unit), 2),
    ]
    count = (
        f"Oferty: aktywne {_count(investment.offers_active)} z {_count(investment.offers_total)}"
        f" · pokazano {len(investment.offers)}"
    )
    if investment.offers_omitted:
        count += f" · pominięto {investment.offers_omitted} (zwiększ --limit)"
    lines = [
        f"{investment.name} [{investment.investment_slug}] · {_status(investment.status)}",
        place,
        f"Deweloper: {investment.developer.name} [{investment.developer.developer_slug}]",
        "Średnio (aktywne oferty): " + " · ".join(averages),
        count + ".",
    ]
    for offer in investment.offers:
        lines.append(_offer_line(offer))
        if offer.price_history is not None:
            lines += [_event_line(event, unit) for event in offer.price_history]
    return "\n".join(lines)


def _offer_line(offer: OfferBase) -> str:
    parts = [f"[{offer.offer_id}] {offer.name}", *_measures(offer), _status(offer.status)]
    if offer.price_change_since_start:  # neither unknown nor zero
        parts.append(f"od pierwszej ceny {_change(offer)}")
    return " · ".join(parts)


def _measures(offer: OfferBase) -> list[str]:
    unit = offer.currency or ""
    return [
        _amount(offer.price, unit),
        _amount(offer.area_m2, "m²", 2),
        _amount(offer.price_per_m2, _per_m2(unit), 2),
    ]


def _per_m2(currency: str) -> str:
    """``PLN/m²``; without a currency no unit at all (not ``/m²``)."""
    return f"{currency}/m²" if currency else ""


def _change(offer: OfferBase) -> str:
    text = _amount(offer.price_change_since_start, offer.currency or "", signed=True)
    pct = offer.price_change_since_start_pct
    return text if pct is None else f"{text} ({_number(pct, 2, signed=True)}%)"


def _event_line(event: PriceEvent, unit: str) -> str:
    day = event.date.isoformat() if event.date else "?"
    return f"  {day:<10}  {_EVENTS.get(event.kind, event.kind):<12}  {_amount(event.price, unit)}"


def _status(status: str) -> str:
    return _STATUSES.get(status, status)


def _count(value: int | None) -> str:
    return "?" if value is None else _number(value)


def _amount(value: float | None, unit: str, decimals: int = 0, *, signed: bool = False) -> str:
    number = "?" if value is None else _number(value, decimals, signed=signed)
    return f"{number} {unit}".rstrip()


def _number(value: float, decimals: int = 0, *, signed: bool = False) -> str:
    """``1234567.5`` -> ``1 234 567,5``: Polish digit groups and decimal comma, no trailing
    zeros; ``signed`` adds ``+`` to positive numbers. Zero is ``0``, never ``-0``/``+0``."""
    text = f"{value:{'+' if signed else ''},.{decimals}f}"
    if decimals:
        text = text.rstrip("0").rstrip(".")
    if text.lstrip("+-") == "0":  # -0.001 rounds to "-0"
        return "0"
    return text.replace(",", " ").replace(".", ",")
