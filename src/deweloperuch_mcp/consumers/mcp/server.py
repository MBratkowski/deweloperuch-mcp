"""``deweloperuch-mcp``: the MCP server over the use cases (D13), stdio only (U3).

An MCP client starts the server and talks to it over stdin/stdout; it has no options
besides ``--help``. Thirteen read-only tools (``TOOLS``): ``search_locations``,
``search_offers``, ``get_offer``, ``search_investments``, ``get_investment``,
``search_developers``, ``get_developer``, ``get_market_statistics``,
``get_transaction_statistics``, ``rank_locations``, ``get_building``,
``estimate_property_value``, ``get_government_statistics``. Four prompts (``PROMPTS``),
conversation starters a person picks in the client: ``znajdz_mieszkanie``,
``ocen_oferte``, ``przeswietl_dewelopera``, ``porownaj_miasta``; each is one user
message that names the tools to use, and calls none itself.

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
- Arguments off the input schema -> an error result in Polish: each field, what its
  schema allows (range, values, type) and what was given (``Server``, D12), instead of
  pydantic's English text. An argument the schema does not name -> an error result
  that names it and lists the tool's arguments; every input schema says so
  (``additionalProperties: false``).

Tools are ``*Tool`` classes in ``tools/`` and prompts ``*Prompt`` classes in ``prompts/``
(D17), with their descriptions. The descriptions are for the model: in Polish, like the
application's messages, and without backend names (no endpoints, no ``invest``/``sale``).
Imports only the use cases, the models, the composition root and the consumers (D16;
tests/architecture/test_layering.py).
"""

import argparse
import json
from collections.abc import AsyncIterator, Callable, Iterable, Sequence
from contextlib import asynccontextmanager
from importlib import metadata
from typing import Any

from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError, UnexpectedToolError
from mcp.server.mcpserver.prompts import Prompt
from mcp.types import CallToolResult, InputRequiredResult
from mcp.types import Tool as McpTool
from pydantic import ValidationError

from deweloperuch_mcp.bootstrap import Session, new_session
from deweloperuch_mcp.consumers.mcp.prompts.assess_offer_prompt import AssessOfferPrompt
from deweloperuch_mcp.consumers.mcp.prompts.check_developer_prompt import CheckDeveloperPrompt
from deweloperuch_mcp.consumers.mcp.prompts.compare_cities_prompt import CompareCitiesPrompt
from deweloperuch_mcp.consumers.mcp.prompts.find_apartment_prompt import FindApartmentPrompt
from deweloperuch_mcp.consumers.mcp.support.calls import SessionContext
from deweloperuch_mcp.consumers.mcp.support.prompt_base import PromptBase
from deweloperuch_mcp.consumers.mcp.support.tool_base import ToolBase
from deweloperuch_mcp.consumers.mcp.tools.estimate_property_value_tool import (
    EstimatePropertyValueTool,
)
from deweloperuch_mcp.consumers.mcp.tools.get_building_tool import GetBuildingTool
from deweloperuch_mcp.consumers.mcp.tools.get_developer_tool import GetDeveloperTool
from deweloperuch_mcp.consumers.mcp.tools.get_government_statistics_tool import (
    GetGovernmentStatisticsTool,
)
from deweloperuch_mcp.consumers.mcp.tools.get_investment_tool import GetInvestmentTool
from deweloperuch_mcp.consumers.mcp.tools.get_market_statistics_tool import GetMarketStatisticsTool
from deweloperuch_mcp.consumers.mcp.tools.get_offer_tool import GetOfferTool
from deweloperuch_mcp.consumers.mcp.tools.get_transaction_statistics_tool import (
    GetTransactionStatisticsTool,
)
from deweloperuch_mcp.consumers.mcp.tools.rank_locations_tool import RankLocationsTool
from deweloperuch_mcp.consumers.mcp.tools.search_developers_tool import SearchDevelopersTool
from deweloperuch_mcp.consumers.mcp.tools.search_investments_tool import SearchInvestmentsTool
from deweloperuch_mcp.consumers.mcp.tools.search_locations_tool import SearchLocationsTool
from deweloperuch_mcp.consumers.mcp.tools.search_offers_tool import SearchOffersTool
from deweloperuch_mcp.consumers.shared.text import printable

SERVER_NAME = "deweloperuch"
DISTRIBUTION = "deweloperuch-mcp"

INSTRUCTIONS = (
    "Dane z deweloperuch.pl o mieszkaniach w Polsce. Typowy plan: search_locations (nazwa "
    "miejsca -> city_slug), search_offers (oferty w mieście z filtrami), potem get_offer "
    "(oferta z historią ceny) albo get_investment (oferty jednej inwestycji). Projekty w "
    "mieście i slug inwestycji po nazwie daje search_investments, slug dewelopera po nazwie "
    "search_developers (dalej get_developer). Ocena ceny oferty: get_offer (price_flags), "
    "potem porównaj z get_market_statistics albo estimate_property_value.\n"
    "\n"
    "Trzy rodzaje cen, nie mieszaj ich: ofertowe deweloperów (search_offers, "
    "get_market_statistics, search_investments); transakcyjne z rejestru RCN "
    "(get_transaction_statistics, rank_locations, get_building, estimate_property_value; "
    "najnowsze okresy są niepełne, get_transaction_statistics oznacza je incomplete); "
    "oficjalne NBP i GUS, obok cen także mieszkania oddane, "
    "bezrobocie i wynagrodzenia (get_government_statistics). Jego location to nazwa miasta "
    "małymi literami bez polskich znaków; nie wymaga "
    "search_locations.\n"
    "\n"
    "Serwis jest projektem społecznym: pytaj oszczędnie i zawężaj filtry zamiast przeglądać "
    "kolejne strony. Gdy błąd narzędzia zawiera STOP, przestań używać tych narzędzi, niczego "
    "nie ponawiaj, nie szukaj obejścia i powiedz o tym użytkownikowi, podając powód z "
    "komunikatu. Dalsze kroki należą do użytkownika; sam niczego nie odblokowuj ani nie "
    "uruchamiaj ponownie. Gdy narzędzie odrzuci argumenty, popraw wskazane pola zgodnie z "
    "komunikatem i ponów. Pola kończące się na _url to linki do stron deweloperuch.pl: "
    "podawaj je użytkownikowi, np. w tabeli ofert."
)


TOOLS: tuple[ToolBase, ...] = (
    SearchLocationsTool(),
    SearchOffersTool(),
    GetOfferTool(),
    SearchInvestmentsTool(),
    GetInvestmentTool(),
    SearchDevelopersTool(),
    GetDeveloperTool(),
    GetMarketStatisticsTool(),
    GetTransactionStatisticsTool(),
    RankLocationsTool(),
    GetBuildingTool(),
    EstimatePropertyValueTool(),
    GetGovernmentStatisticsTool(),
)
"""The tools in the order ``tools/list`` gives them."""


PROMPTS: tuple[PromptBase, ...] = (
    FindApartmentPrompt(),
    AssessOfferPrompt(),
    CheckDeveloperPrompt(),
    CompareCitiesPrompt(),
)
"""The prompts in the order ``prompts/list`` gives them."""


# --- the server ----------------------------------------------------------------------------

_CLOSED = {"additionalProperties": False}


UNKNOWN_SHOWN = 10
"""Unknown argument names an error lists, at most; each cut to ``NAME_SHOWN`` characters."""
NAME_SHOWN = 60


def unknown_arguments(tool: str, given: Iterable[str], allowed: Iterable[str]) -> str | None:
    """The message for argument names ``tool`` does not take; ``None`` if there are none.

    The names come from the caller, so they are shown escaped (``printable``) and cut.
    """
    known = list(allowed)
    unknown = sorted(set(given) - set(known))
    if not unknown:
        return None
    shown = ", ".join(f"'{printable(name[:NAME_SHOWN])}'" for name in unknown[:UNKNOWN_SHOWN])
    more = f" (i {len(unknown) - UNKNOWN_SHOWN} innych)" if len(unknown) > UNKNOWN_SHOWN else ""
    noun = "Nieznany argument" if len(unknown) == 1 else "Nieznane argumenty"
    return (
        f"{noun} narzędzia {tool}: {shown}{more}. Dozwolone argumenty: {', '.join(known)}. "
        "Popraw nazwy i ponów; nic nie zostało wysłane."
    )


GIVEN_SHOWN = 60
"""Characters of a rejected value an error repeats, at most."""


def _allowed(schema: dict[str, Any]) -> str | None:
    """What a field's schema allows, in words: values, a range of whole numbers, a type;
    ``None`` for a schema these words do not cover."""
    options = schema.get("anyOf", [schema])
    concrete = [option for option in options if option.get("type") != "null"]
    if len(concrete) != 1:
        return None
    option = concrete[0]
    low, high = option.get("minimum"), option.get("maximum")
    if "enum" in option:
        rule = "jedną z wartości " + ", ".join(map(str, option["enum"]))
    elif option.get("type") == "integer" and low is not None and high is not None:
        rule = f"liczbą całkowitą z zakresu {low}–{high}"
    elif option.get("type") == "integer":
        rule = "liczbą całkowitą" + ("" if low is None else f" nie mniejszą niż {low}")
    elif option.get("type") == "number" and low is not None and high is not None:
        rule = f"liczbą z zakresu {low:g}–{high:g} (z kropką dziesiętną)"
    elif option.get("type") == "number":
        rule = "liczbą (z kropką dziesiętną)"
    elif option.get("type") == "boolean":
        rule = "true albo false"
    elif option.get("type") == "string":
        rule = "tekstem"
    else:
        return None
    return rule + (" albo pusty" if len(concrete) < len(options) else "")


def invalid_arguments(tool: str, error: ValidationError, fields: dict[str, dict[str, Any]]) -> str:
    """The message for arguments off ``tool``'s input schema: each field (once), what its
    schema allows and what was given (escaped, cut: the caller's data)."""
    parts: dict[str, str] = {}
    for found in error.errors(include_url=False):
        name = printable(str(found["loc"][0])) if found["loc"] else "argumenty"
        if name in parts:
            continue
        if found["type"] == "missing":
            parts[name] = f"{name}: brak wymaganego argumentu"
            continue
        given = printable(json.dumps(found.get("input"), ensure_ascii=False, default=repr))
        given = given[:GIVEN_SHOWN]
        allowed = _allowed(fields.get(name, {}))
        parts[name] = (
            f"{name} ma niepoprawną wartość {given}"
            if allowed is None
            else f"{name} musi być {allowed}, podano {given}"
        )
    noun = "Błędny argument" if len(parts) == 1 else "Błędne argumenty"
    return (
        f"{noun} narzędzia {tool}: {'; '.join(parts.values())}. Popraw i ponów; nic nie "
        "zostało wysłane."
    )


class Server(MCPServer[Session]):
    """``MCPServer`` that words errors of arguments off the input schema in Polish, refuses
    arguments its tools do not take, and whose input schemas say so.

    The SDK raises the former from ``call_tool`` as ``ToolError`` caused by pydantic's
    ``ValidationError`` and shows the model ``str(error)``: English, with links to
    pydantic's docs. Its text is replaced (``invalid_arguments``), and the cause stays,
    so the SDK still logs just the names of the rejected fields. Any other error passes
    unchanged, ``UnexpectedToolError`` too (the SDK logs it as a crash). The signature is
    ``MCPServer.call_tool``'s; the SDK has no upper version bound, so
    tests/unit/consumers/mcp/test_server.py catches a change at an update.
    """

    async def list_tools(self) -> list[McpTool]:
        """The tools, each input schema closed to other arguments (``additionalProperties``)."""
        return [
            tool.model_copy(update={"input_schema": {**tool.input_schema, **_CLOSED}})
            for tool in await super().list_tools()
        ]

    async def call_tool(
        self, name: str, arguments: dict[str, Any], context: SessionContext | None = None
    ) -> CallToolResult | InputRequiredResult:
        """An argument the tool does not take is refused before the tool runs (the SDK
        would drop it silently: a model's ``max_price`` would search without a limit)."""
        tool = next((t for t in await super().list_tools() if t.name == name), None)
        fields: dict[str, dict[str, Any]] = {}
        if tool is not None:
            fields = tool.input_schema.get("properties", {})
            refused = unknown_arguments(name, arguments, fields)
            if refused is not None:
                raise ToolError(refused)
        try:
            return await super().call_tool(name, arguments, context)
        except UnexpectedToolError:
            raise
        except ToolError as err:
            if not isinstance(err.__cause__, ValidationError):
                raise
            raise ToolError(invalid_arguments(name, err.__cause__, fields)) from err.__cause__


def build_server(
    open_session: Callable[[], Session] | None = None,
) -> MCPServer[Session]:
    """The server with its tools (``TOOLS``) and prompts (``PROMPTS``); each run opens one
    session with ``open_session`` (default: ``bootstrap.new_session``, looked up when the
    server starts)."""

    @asynccontextmanager
    async def lifespan(_: MCPServer[Session]) -> AsyncIterator[Session]:
        opener = new_session if open_session is None else open_session
        with opener() as session:
            yield session

    server = Server(
        name=SERVER_NAME, version=_version(), instructions=INSTRUCTIONS, lifespan=lifespan
    )
    for tool in TOOLS:
        server.add_tool(
            tool.handler(),
            name=tool.name,
            title=tool.title,
            description=tool.description,
            annotations=tool.annotations,
        )
    for prompt in PROMPTS:
        server.add_prompt(
            Prompt.from_function(
                prompt.render, name=prompt.name, title=prompt.title, description=prompt.description
            )
        )
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
