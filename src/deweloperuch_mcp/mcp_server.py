"""``deweloperuch-mcp``: the MCP server over the domain services (D6), stdio only (U3).

An MCP client starts the server and talks to it over stdin/stdout; it has no options
besides ``--help``. Four read-only tools: ``search_locations``, ``search_offers``,
``get_offer``, ``get_investment``.

- One ``services.Session`` for the life of the server (the lifespan opens it and closes
  it on exit), so every call shares the limiter, the cache and the STOP latch. A STOP
  recorded by any process (CLI, recon) stops the tools too; no tool removes it (only a
  person, with the CLI), and after a STOP the server needs a restart. Texts for the
  model (instructions, STOP messages) say only "stop and report": nothing about
  lifting the STOP or restarting, which is the user's call.
- The services are synchronous; each call runs in a worker thread
  (``asyncio.to_thread``), so parallel calls do not block the event loop. The limiter
  still sends one request at a time.
- Results are the MCP representation of the domain results (``mcp_results``: compact
  search items, no ``null`` fields), structured (output schema) and repeated as compact
  JSON text for clients without structured output. Lists carry ``total``, ``returned``
  and ``truncated`` (D4).
- ``DeweloperuchError`` -> an error result (``isError``) with its message, which says
  what to change or that the series stopped (STOP); its ``detail`` (paths, statuses,
  bodies) goes only to the server log. Anything else -> a generic message; the
  traceback goes to the log. The log is stderr: stdout is the protocol.

Tool descriptions and field descriptions are for the model: in Polish, like the
services' messages, and without backend names (no endpoints, no ``invest``/``sale``).
Imports from the package only ``services``, ``errors``, ``domain.models`` and
``mcp_results``, never the client (D6; tests/test_layering.py).
"""

import argparse
import asyncio
import logging
import re
from collections.abc import AsyncIterator, Callable, Sequence
from contextlib import asynccontextmanager
from importlib import metadata
from typing import Annotated, Any, Literal

from mcp.server.mcpserver import Context, MCPServer
from mcp.types import CallToolResult, TextContent, ToolAnnotations
from pydantic import BeforeValidator, Field

from deweloperuch_mcp import mcp_results, services
from deweloperuch_mcp.errors import DeweloperuchError, ServiceBlockedError
from deweloperuch_mcp.mcp_results import (
    InvestmentResult,
    LocationsResult,
    McpModel,
    OfferResult,
    OffersResult,
)

logger = logging.getLogger(__name__)

SERVER_NAME = "deweloperuch"
DISTRIBUTION = "deweloperuch-mcp"

McpPerPage = Literal[10, 50]
"""Page sizes of ``search_offers`` in MCP: [P] values that keep a result readable."""

DEFAULT_INVESTMENT_LIMIT = 20
"""Offers ``get_investment`` returns unless asked otherwise (about 6k characters)."""
MAX_INVESTMENT_LIMIT = 200

UNEXPECTED_ERROR = (
    "Nieoczekiwany błąd serwera MCP deweloperuch (szczegóły są w jego logu). "
    "Nie ponawiaj tego wywołania; zgłoś problem użytkownikowi."
)

INSTRUCTIONS = (
    "Dane z deweloperuch.pl: ceny ofertowe mieszkań od deweloperów (rynek pierwotny) w "
    "Polsce, z historią zmian cen. Typowa kolejność: search_locations (nazwa miejsca -> "
    "city_slug), search_offers (oferty w mieście z filtrami ceny i metrażu), potem "
    "get_investment (oferty jednej inwestycji) albo get_offer (jedna oferta z historią "
    "ceny). Serwis jest projektem społecznym: pytaj oszczędnie i zawężaj filtry zamiast "
    "przeglądać kolejne strony. Gdy błąd narzędzia zawiera STOP, przestań używać tych "
    "narzędzi, niczego nie ponawiaj, nie szukaj obejścia i powiedz o tym użytkownikowi, "
    "podając powód z komunikatu. Dalsze kroki należą do użytkownika; sam niczego nie "
    "odblokowuj ani nie uruchamiaj ponownie. Błędy walidacji argumentów bywają po "
    "angielsku: popraw wskazane pole zgodnie ze schematem i ponów."
)

# Read-only: nothing changes anywhere. Open world: the data comes from an outside service
# and changes over time. idempotentHint and destructiveHint are left out: the spec gives
# them meaning only for tools that are not read-only.
READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=True)

SessionContext = Context[services.Session, Any]


# --- arguments as models send them ---------------------------------------------------------

# One rule for every number: JSON integers, or text of digits only ("10", " 10 "), never
# "10.0" nor true/false. Optional arguments: "" and null mean "not given"; arguments with
# a default: null means the default. Choices are trimmed (" price_asc ").
_INTEGER = re.compile(r"[+-]?\d{1,18}")


def _whole_number(value: object) -> object:
    """``"10"`` -> ``10`` (models sometimes send numbers as text)."""
    if isinstance(value, bool):
        raise ValueError("oczekiwano liczby całkowitej, a nie true/false")
    if isinstance(value, str):
        text = value.strip()
        if not _INTEGER.fullmatch(text):
            raise ValueError(f"oczekiwano liczby całkowitej zapisanej cyframi, podano {value!r}")
        return int(text)
    return value


def _blank_is_none(value: object) -> object:
    """``""`` for an optional argument means "not given"; other text is trimmed."""
    if isinstance(value, str):
        return value.strip() or None
    return value


def _optional_whole_number(value: object) -> object:
    blank = _blank_is_none(value)
    return None if blank is None else _whole_number(blank)


def _whole_or(default: int) -> BeforeValidator:
    """A whole number; ``null`` means ``default``."""
    return BeforeValidator(lambda value: _whole_number(default if value is None else value))


def _null_is(default: object) -> BeforeValidator:
    return BeforeValidator(lambda value: default if value is None else value)


WholeNumber = BeforeValidator(_whole_number)
OptionalWholeNumber = BeforeValidator(_optional_whole_number)
OptionalChoice = BeforeValidator(_blank_is_none)

# Bounds on the number itself, so the schema shows them inside `anyOf` with null.
# (A BeforeValidator before Field(ge=...) would leave raw "ge"/"le" in the schema.)
Price = Annotated[int, Field(ge=0, le=services.PRICE_LIMIT)]
Area = Annotated[int, Field(ge=0, le=services.AREA_LIMIT)]
Page = Annotated[int, Field(ge=1, le=services.MAX_PAGES)]
OfferId = Annotated[int, Field(ge=1)]
Limit = Annotated[int, Field(ge=0, le=MAX_INVESTMENT_LIMIT)]


# --- tools ---------------------------------------------------------------------------------

# [W] docs/discovery/endpoints.md, location-search: `count` (offer_count of districts and
# streets) is the number of offers, hence "wg serwisu"; truncated is a heuristic for the
# suggestions (services.search_locations), hence "może być więcej".
SEARCH_LOCATIONS = """\
Znajduje miasta, dzielnice i ulice w Polsce po fragmencie nazwy. Użyj na początku, \
żeby zamienić nazwę miejsca na city_slug, którego wymaga search_offers. Nie zwraca \
ofert ani cen.

Zwraca items (kind: city, district albo street; name, city, city_slug, opcjonalnie \
district, street, lat, lng i offer_count, czyli liczbę ofert wg serwisu) oraz total, \
returned, truncated i hint. total jest null, gdy wyników jest więcej niż pokazano; \
truncated=true znaczy, że pasujących może być więcej: doprecyzuj nazwę. Miejscowości z \
offer_count=0 nie mają ofert: nie przekazuj ich do search_offers. Dzielnica i ulica \
podają city_slug swojego miasta; search_offers filtruje tylko po mieście."""

SEARCH_OFFERS = """\
Wyszukuje oferty mieszkań od deweloperów (tylko rynek pierwotny, ceny ofertowe, nie \
transakcyjne) w jednym mieście albo w całej Polsce (city=polska), z filtrami ceny i \
metrażu i sortowaniem po cenie. Użyj, gdy szukasz mieszkań w budżecie albo o danym \
metrażu. Nie filtruje po dzielnicy, liczbie pokoi ani deweloperze.

Zwraca jedną stronę: total (wszystkie pasujące), returned, page, per_page, \
pages_available, truncated, hint i items (offer_id, investment_slug, name, cena w PLN, \
metraż w m², cena za m², status, inwestycja, deweloper, ostatnia zmiana ceny i zmiana \
od pierwszej ceny w procentach; miasto tylko przy city=polska). Pozycje są skrócone; \
szczegóły oferty i historię ceny daje get_offer.

Ograniczenia: można przejrzeć najwyżej 20 stron po per_page ofert. Gdy truncated=true, \
zawęź filtry zamiast przeglądać kolejne strony. Wszystkie oferty jednej inwestycji daje \
get_investment."""

GET_OFFER = """\
Zwraca jedną ofertę z pełną historią ceny, inwestycją i deweloperem. Użyj, gdy chcesz \
zobaczyć, jak zmieniała się cena mieszkania. Wymaga offer_id i investment_slug (oba \
podaje search_offers albo get_investment): samo offer_id nie wystarcza.

Zwraca cenę, metraż, cenę za m², status (active albo archived), zmianę od pierwszej \
ceny, daty i price_history (date, kind: offer, archived albo restored, price). Do listy \
ofert jednej inwestycji użyj get_investment."""

GET_INVESTMENT = """\
Zwraca inwestycję (projekt deweloperski): miasto, ulicę, współrzędne, dewelopera, \
średnie ceny aktywnych ofert, liczbę ofert i listę ofert (najpierw aktywne, potem \
archiwalne). Użyj, gdy chcesz zobaczyć mieszkania jednego projektu. investment_slug \
podaje search_offers.

Ograniczenia: zwraca najwyżej limit ofert (domyślnie 20); offers_returned mówi, ile ich \
jest na liście, truncated i offers_omitted, czy i ile pominięto. offers_total to liczba \
z serwisu, a pominięte oferty liczy offers_omitted. Przy dużej inwestycji nie zwiększaj \
limitu bez potrzeby; offers_omitted > 0 znaczy, że lista jest niepełna. \
include_history=true dodaje historię ceny każdej zwróconej oferty: wynik jest dłuższy i \
powstaje wolniej. Dla jednej oferty lepiej użyć get_offer."""


async def search_locations(
    query: Annotated[
        str,
        Field(
            title="Szukany tekst",
            description=(
                "Fragment nazwy miasta, dzielnicy lub ulicy, 2–100 znaków, z polskimi "
                "znakami, np. Kraków, Mokotów."
            ),
        ),
    ],
    ctx: SessionContext,
) -> Annotated[CallToolResult, LocationsResult]:
    session = _session(ctx)
    return await _run(lambda: mcp_results.locations(services.search_locations(session, query)))


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
        services.OfferSort | None,
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
        Page, _whole_or(1), Field(title="Strona", description="Numer strony wyników, 1–20.")
    ] = 1,
    per_page: Annotated[
        McpPerPage,
        _whole_or(services.DEFAULT_PER_PAGE),
        Field(
            title="Ofert na stronie",
            description=(
                "10 albo 50. Pozycja to ok. 350 znaków wyniku, więc 50 daje ok. 17 tys.; "
                "zwykle wystarcza 10."
            ),
        ),
    ] = 10,
) -> Annotated[CallToolResult, OffersResult]:
    session = _session(ctx)
    return await _run(
        lambda: mcp_results.offers(
            services.search_offers(
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
            whole_country=city.strip() == services.WHOLE_COUNTRY,
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
    session = _session(ctx)
    return await _run(
        lambda: mcp_results.offer(services.get_offer(session, offer_id, investment_slug))
    )


async def get_investment(
    investment_slug: Annotated[
        str,
        Field(title="Inwestycja", description="investment_slug z search_offers, np. smolna."),
    ],
    ctx: SessionContext,
    include_history: Annotated[
        bool,
        _null_is(False),
        Field(
            title="Z historią cen",
            description="true: dołącz historię ceny każdej zwróconej oferty (dłuższy wynik).",
        ),
    ] = False,
    limit: Annotated[
        Limit,
        _whole_or(DEFAULT_INVESTMENT_LIMIT),
        Field(
            title="Limit ofert",
            description=(
                "Najwięcej ofert w wyniku (najpierw aktywne), domyślnie 20, 0 = tylko "
                "podsumowanie inwestycji. Ile pominięto, mówi offers_omitted. Każda oferta "
                "to ok. 300 znaków wyniku, z historią ceny kilkaset więcej. Maksimum 200 "
                "daje ok. 60 tys. znaków; zwykle wystarcza domyślne 20."
            ),
        ),
    ] = DEFAULT_INVESTMENT_LIMIT,
) -> Annotated[CallToolResult, InvestmentResult]:
    session = _session(ctx)
    return await _run(
        lambda: mcp_results.investment(
            services.get_investment(
                session, investment_slug, include_history=include_history, limit=limit
            )
        )
    )


TOOLS: tuple[tuple[Callable[..., Any], str, str], ...] = (
    (search_locations, "Szukaj lokalizacji", SEARCH_LOCATIONS),
    (search_offers, "Szukaj ofert mieszkań", SEARCH_OFFERS),
    (get_offer, "Oferta z historią ceny", GET_OFFER),
    (get_investment, "Inwestycja z ofertami", GET_INVESTMENT),
)


# --- the server ----------------------------------------------------------------------------


def build_server(
    open_session: Callable[[], services.Session] | None = None,
) -> MCPServer[services.Session]:
    """The server with its four tools; each run opens one session with ``open_session``
    (default: ``services.Session``, looked up when the server starts)."""

    @asynccontextmanager
    async def lifespan(_: MCPServer[services.Session]) -> AsyncIterator[services.Session]:
        opener = services.Session if open_session is None else open_session
        with opener() as session:
            yield session

    server = MCPServer(
        name=SERVER_NAME, version=_version(), instructions=INSTRUCTIONS, lifespan=lifespan
    )
    for tool, title, description in TOOLS:
        server.add_tool(tool, title=title, description=description, annotations=READ_ONLY)
    return server


def main(argv: Sequence[str] | None = None) -> None:
    """Entry point of the ``deweloperuch-mcp`` script."""
    parser = argparse.ArgumentParser(
        prog="deweloperuch-mcp",
        description=(
            "Serwer MCP z danymi deweloperuch.pl (ceny ofertowe mieszkań, tylko odczyt). "
            "Uruchamia go klient MCP; serwer rozmawia z nim przez stdin/stdout (stdio)."
        ),
        add_help=False,
    )
    parser.add_argument("-h", "--help", action="help", help="pokaż tę pomoc i zakończ")
    parser.parse_args(argv)
    build_server().run("stdio")


# --- helpers -------------------------------------------------------------------------------


def _version() -> str:
    try:
        return metadata.version(DISTRIBUTION)
    except metadata.PackageNotFoundError:  # a source tree that is not installed
        return "0+unknown"


def _session(ctx: SessionContext) -> services.Session:
    return ctx.request_context.lifespan_context


async def _run(call: Callable[[], McpModel]) -> CallToolResult:
    """``call`` in a worker thread: its result, or a tool error with the message only."""
    try:
        result = await asyncio.to_thread(call)
    except ServiceBlockedError as err:
        logger.warning("%s Szczegóły: %s", err, err.detail)
        return _error(str(err))
    except DeweloperuchError as err:
        logger.info("%s: %s Szczegóły: %s", type(err).__name__, err, err.detail)
        return _error(str(err))
    except Exception:
        logger.exception("Nieoczekiwany błąd narzędzia")
        return _error(UNEXPECTED_ERROR)
    return CallToolResult(
        content=[TextContent(type="text", text=mcp_results.dump_json(result))],
        structured_content=mcp_results.dump(result),
    )


def _error(message: str) -> CallToolResult:
    return CallToolResult(content=[TextContent(type="text", text=message)], is_error=True)
