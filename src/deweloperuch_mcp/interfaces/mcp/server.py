"""``deweloperuch-mcp``: the MCP server over the use cases (D13), stdio only (U3).

An MCP client starts the server and talks to it over stdin/stdout; it has no options
besides ``--help``. Five read-only tools: ``search_locations``, ``search_offers``,
``get_offer``, ``get_investment``, ``get_government_statistics``.

- One session (``bootstrap.new_session``) for the life of the server (the lifespan opens
  it and closes it on exit), so every call shares the limiter, the cache and the STOP latch. A STOP
  recorded by any process (CLI, recon) stops the tools too; no tool removes it (only a
  person, with the CLI), and after a STOP the server needs a restart. Texts for the
  model (instructions, STOP messages) say only "stop and report": nothing about
  lifting the STOP or restarting, which is the user's call.
- The use cases are synchronous; each call runs in a worker thread
  (``asyncio.to_thread``), so parallel calls do not block the event loop. The limiter
  still sends one request at a time.
- Results are the MCP representation of the results (``presenters``: compact
  search items, no ``null`` fields), structured (output schema) and repeated as compact
  JSON text for clients without structured output. Lists carry ``total``, ``returned``
  and ``truncated`` (D4).
- ``DeweloperuchError`` -> an error result (``isError``) with its message, which says
  what to change or that the series stopped (STOP); its ``detail`` (paths, statuses,
  bodies) goes only to the server log. Anything else -> a generic message; the
  traceback goes to the log. The log is stderr: stdout is the protocol.
- Arguments off the input schema -> the SDK's error result (field, rule, value), without
  the link to pydantic's docs it adds under each error (``Server``, D12).

Tools live in one module per capability, with their descriptions; the descriptions are
for the model: in Polish, like the application's messages, and without backend names (no
endpoints, no ``invest``/``sale``). Imports only the application, the domain, the
composition root and the interfaces (D13; tests/test_layering.py).
"""

import argparse
import re
from collections.abc import AsyncIterator, Callable, Sequence
from contextlib import asynccontextmanager
from importlib import metadata
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError, UnexpectedToolError
from mcp.types import CallToolResult, InputRequiredResult, ToolAnnotations
from pydantic import ValidationError

from deweloperuch_mcp.bootstrap import Session, new_session
from deweloperuch_mcp.interfaces.mcp.calls import SessionContext
from deweloperuch_mcp.interfaces.mcp.investments import GET_INVESTMENT, get_investment
from deweloperuch_mcp.interfaces.mcp.locations import SEARCH_LOCATIONS, search_locations
from deweloperuch_mcp.interfaces.mcp.offers import (
    GET_OFFER,
    SEARCH_OFFERS,
    get_offer,
    search_offers,
)
from deweloperuch_mcp.interfaces.mcp.statistics import (
    GET_GOVERNMENT_STATISTICS,
    get_government_statistics,
)

SERVER_NAME = "deweloperuch"
DISTRIBUTION = "deweloperuch-mcp"

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
    "angielsku: popraw wskazane pole zgodnie ze schematem i ponów. Pola kończące się na "
    "_url to linki do stron deweloperuch.pl: podawaj je użytkownikowi, np. w tabeli ofert. "
    "Oficjalne statystyki GUS i NBP dla Polski i miast (mieszkania oddane i rozpoczęte, "
    "ceny NBP, bezrobocie, wynagrodzenia) daje get_government_statistics; to dane rynkowe, "
    "nie oferty, i nie wymagają wcześniejszego search_locations."
)

# Read-only: nothing changes anywhere. Open world: the data comes from an outside service
# and changes over time. idempotentHint and destructiveHint are left out: the spec gives
# them meaning only for tools that are not read-only.
READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=True)


TOOLS: tuple[tuple[Callable[..., Any], str, str], ...] = (
    (search_locations, "Szukaj lokalizacji", SEARCH_LOCATIONS),
    (search_offers, "Szukaj ofert mieszkań", SEARCH_OFFERS),
    (get_offer, "Oferta z historią ceny", GET_OFFER),
    (get_investment, "Inwestycja z ofertami", GET_INVESTMENT),
    (get_government_statistics, "Statystyki GUS i NBP", GET_GOVERNMENT_STATISTICS),
)


# --- the server ----------------------------------------------------------------------------

# The line pydantic puts under each validation error: a link to its docs, not a rule of
# the tool. The model needs the field and the rule (D12: no library details).
_DOCS_LINK = re.compile(r"\s*For further information visit https?://errors\.pydantic\.dev/\S*\s*")


class Server(MCPServer[Session]):
    """``MCPServer`` whose errors for arguments off the input schema carry no docs links.

    The SDK raises them from ``call_tool`` as ``ToolError`` caused by pydantic's
    ``ValidationError`` and shows the model ``str(error)``. Only the docs-link lines are
    dropped from that text, and the cause stays, so the SDK still logs just the names of
    the rejected fields. Any other error passes unchanged, ``UnexpectedToolError`` too
    (the SDK logs it as a crash). The signature is ``MCPServer.call_tool``'s; the SDK has
    no upper version bound, so tests/test_mcp_server.py catches a change at an update.
    """

    async def call_tool(
        self, name: str, arguments: dict[str, Any], context: SessionContext | None = None
    ) -> CallToolResult | InputRequiredResult:
        try:
            return await super().call_tool(name, arguments, context)
        except UnexpectedToolError:
            raise
        except ToolError as err:
            if not isinstance(err.__cause__, ValidationError):
                raise
            lines = str(err).splitlines()
            text = "\n".join(line for line in lines if not _DOCS_LINK.fullmatch(line))
            raise ToolError(text) from err.__cause__


def build_server(
    open_session: Callable[[], Session] | None = None,
) -> MCPServer[Session]:
    """The server with its tools (``TOOLS``); each run opens one session with ``open_session``
    (default: ``bootstrap.new_session``, looked up when the server starts)."""

    @asynccontextmanager
    async def lifespan(_: MCPServer[Session]) -> AsyncIterator[Session]:
        opener = new_session if open_session is None else open_session
        with opener() as session:
            yield session

    server = Server(
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


def _version() -> str:
    try:
        return metadata.version(DISTRIBUTION)
    except metadata.PackageNotFoundError:  # a source tree that is not installed
        return "0+unknown"
