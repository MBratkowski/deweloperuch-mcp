"""D16 (D13 in substance): the direction of dependencies between the layers, checked on
the source (AST).

    consumers  ->  usecases  ->  models
    api        ->  usecases.ports, models
    bootstrap  ->  api, usecases, models

- ``models``: the standard library (``MODELS_STDLIB``) and ``models`` only (no pydantic,
  no I/O libraries, nothing else of the package);
- ``usecases``: the standard library (``USECASES_STDLIB``), ``models`` and ``usecases``;
  never ``api``, the composition root nor the consumers;
- ``api``: ``models``, the ports it implements (``usecases.ports``), ``api``, the stdlib
  modules shared with ``recon/`` (``SHARED``) and third-party libraries; never the rest
  of ``usecases``, the composition root nor the consumers;
- ``bootstrap``: anything below the consumers;
- the stdlib modules shared with ``recon/``: only each other
  (tests/recon_scripts/test_recon_config.py checks they stay stdlib-only);
- ``consumers`` (``CONSUMER_RULES``), never ``api`` nor the modules shared with
  ``recon/`` (the composition root hands them over):
  - ``consumers.shared`` (what both present): ``usecases``, ``models``, itself, pydantic;
  - ``consumers.cli``: ``usecases``, ``models``, ``bootstrap``, ``consumers.shared``,
    itself, typer and pydantic; never ``consumers.mcp``;
  - ``consumers.mcp``: the same with mcp instead of typer; never ``consumers.cli``;
- the entry points of ``[project.scripts]`` (``cli``, ``mcp_server``) are shims: only
  the consumers; the ``errors`` module re-exports the models' errors and the consumers'
  ``printable``.

Checked on the source, since importing a module loads what it imports anyway. Every
module of the package must belong to a layer (``test_every_module_has_a_layer``).
"""

import ast
import sys
from pathlib import Path

import pytest

from support.checks.layering import (
    INTERFACE_WORDS,
    MODELS_STDLIB,
    PACKAGE,
    SOURCE,
    message_texts,
    source_of,
)

SHARED = frozenset(
    f"{PACKAGE}.{name}"
    for name in ("identity", "throttle", "http_policy", "retry_after", "allowlist", "flight")
)
"""Stdlib-only modules ``recon/`` imports at these paths."""


USECASES_STDLIB = MODELS_STDLIB | {"contextlib"}
"""The use cases also scope the wording of failures (``contextlib.contextmanager``)."""

MODELS, USECASES, API = (f"{PACKAGE}.models", f"{PACKAGE}.usecases", f"{PACKAGE}.api")
PORTS = f"{USECASES}.ports"
"""The part of ``usecases`` that ``api`` implements."""
BOOTSTRAP = f"{PACKAGE}.bootstrap"
CONSUMERS = f"{PACKAGE}.consumers"
SHIMS = frozenset({f"{PACKAGE}.cli", f"{PACKAGE}.mcp_server"})
"""The modules ``[project.scripts]`` names: they only hand over to the consumers."""
PRESENTATION, CLI, MCP = f"{CONSUMERS}.shared", f"{CONSUMERS}.cli", f"{CONSUMERS}.mcp"
CONSUMER_RULES: dict[str, tuple[tuple[str, ...], frozenset[str]]] = {
    PRESENTATION: ((USECASES, MODELS, PRESENTATION), frozenset({"pydantic"})),
    CLI: ((USECASES, MODELS, BOOTSTRAP, PRESENTATION, CLI), frozenset({"typer", "pydantic"})),
    MCP: ((USECASES, MODELS, BOOTSTRAP, PRESENTATION, MCP), frozenset({"mcp", "pydantic"})),
    CONSUMERS: ((), frozenset()),
}
"""Each consumer package: the package's modules and the third-party libraries it may
import (``consumers`` itself: nothing)."""


def consumer_rule(module: str) -> tuple[tuple[str, ...], frozenset[str]]:
    return next(rule for prefix, rule in CONSUMER_RULES.items() if within(module, prefix))


def is_module(name: str) -> bool:
    path = SOURCE.parent.joinpath(*name.split("."))
    return path.with_suffix(".py").is_file() or (path / "__init__.py").is_file()


def imported_modules(source: str) -> set[str]:
    """Every module a source imports, anywhere in it; ``from a import b`` counts as ``a``
    and, when ``b`` is a module of the package, as ``a.b`` too."""
    modules: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, "relative imports hide what is imported"
            assert node.module is not None
            modules.add(node.module)
            for alias in node.names:
                name = f"{node.module}.{alias.name}"
                if node.module.split(".")[0] == PACKAGE and is_module(name):
                    modules.add(name)
    return modules


def within(module: str, *prefixes: str) -> bool:
    return any(module == prefix or module.startswith(prefix + ".") for prefix in prefixes)


def own(modules: set[str]) -> set[str]:
    """The package's modules, without the root package itself (its ``__init__`` imports
    nothing)."""
    return {m for m in modules if m.split(".")[0] == PACKAGE} - {PACKAGE}


def stdlib(module: str) -> bool:
    return module.split(".")[0] in sys.stdlib_module_names


def module_name(path: Path) -> str:
    parts = path.relative_to(SOURCE.parent).with_suffix("").parts
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def layer(module: str) -> str:
    for prefix, name in ((MODELS, "models"), (USECASES, "usecases"), (API, "api")):
        if within(module, prefix):
            return name
    if module in SHARED:
        return "shared"
    if module == BOOTSTRAP:
        return "bootstrap"
    if within(module, CONSUMERS):
        return "consumers"
    if module in SHIMS:
        return "shim"
    if module == f"{PACKAGE}.errors":
        return "errors"
    if module == PACKAGE:
        return "package"
    return "?"


def api_may_import(module: str) -> bool:
    """``models``, ``api``, the ports and the shared modules; the bare ``usecases``
    package too (``from deweloperuch_mcp.usecases import ports``), whose ``__init__``
    imports nothing: each of its other modules counts on its own."""
    return within(module, MODELS, PORTS, API) or module in SHARED | {USECASES}


def violations(module: str, source: str) -> set[str]:
    """What ``module`` (whose code is ``source``) imports against its layer's rule."""
    modules = imported_modules(source)
    mine = own(modules)
    others = modules - mine - {PACKAGE}
    match layer(module):
        case "models":
            return {m for m in mine if not within(m, MODELS)} | (others - MODELS_STDLIB)
        case "usecases":
            bad = {m for m in mine if not within(m, MODELS, USECASES)}
            return bad | (others - USECASES_STDLIB)
        case "api":
            return {m for m in mine if not api_may_import(m)}
        case "bootstrap":
            return {m for m in mine if not (within(m, MODELS, USECASES, API) or m in SHARED)}
        case "shared":
            return {m for m in mine if m not in SHARED} | {m for m in others if not stdlib(m)}
        case "errors":
            return mine - {f"{MODELS}.errors", f"{CONSUMERS}.shared.text"} | others
        case "consumers":
            allowed, libraries = consumer_rule(module)
            bad = {m for m in mine if not within(m, *allowed)}
            return bad | {m for m in others if not stdlib(m) and m.split(".")[0] not in libraries}
        case "shim":
            return {m for m in mine if not within(m, CONSUMERS)} | others
        case "package":
            return modules
        case _:
            raise AssertionError(f"{module}: moduł bez warstwy")


MODULES = sorted(module_name(path) for path in SOURCE.rglob("*.py"))


def test_every_module_has_a_layer() -> None:
    assert {module: layer(module) for module in MODULES if layer(module) == "?"} == {}
    assert {"models", "usecases", "api", "bootstrap", "shared", "consumers"} <= {
        layer(module) for module in MODULES
    }


def test_the_ports_are_a_module_of_the_use_cases() -> None:
    assert PORTS in MODULES


@pytest.mark.parametrize("module", MODULES)
def test_each_module_imports_only_what_its_layer_may(module: str) -> None:
    assert violations(module, source_of(module)) == set()


@pytest.mark.parametrize("module", [m for m in MODULES if layer(m) == "models"])
def test_the_models_import_nothing_of_the_package_but_themselves(module: str) -> None:
    assert {m for m in own(imported_modules(source_of(module))) if not within(m, MODELS)} == set()


@pytest.mark.parametrize("module", [m for m in MODULES if layer(m) == "usecases"])
def test_the_use_cases_never_import_the_api_nor_the_consumers(module: str) -> None:
    above = (API, BOOTSTRAP, CONSUMERS, *SHIMS, *SHARED)
    assert {m for m in own(imported_modules(source_of(module))) if within(m, *above)} == set()


@pytest.mark.parametrize("module", [m for m in MODULES if layer(m) == "api"])
def test_the_api_imports_nothing_above_it(module: str) -> None:
    """The client knows the service, the models it maps to and the ports it implements,
    nothing above them: not the use cases, the composition root nor the consumers."""
    modules = own(imported_modules(source_of(module))) - {USECASES}
    above = (USECASES, BOOTSTRAP, CONSUMERS, *SHIMS)

    assert {m for m in modules if within(m, *above) and not within(m, PORTS)} == set()


@pytest.mark.parametrize(
    ("shim", "consumer"),
    [
        (f"{PACKAGE}.cli", f"{CONSUMERS}.cli.app"),
        (f"{PACKAGE}.mcp_server", f"{CONSUMERS}.mcp.server"),
    ],
)
def test_the_entry_points_only_hand_over_to_the_consumers(shim: str, consumer: str) -> None:
    assert own(imported_modules(source_of(shim))) == {consumer}


@pytest.mark.parametrize("module", [m for m in MODULES if layer(m) == "api"])
def test_the_api_never_imports_the_consumers(module: str) -> None:
    """Nothing the consumers present (views, texts, links' wording) is the client's."""
    assert {m for m in own(imported_modules(source_of(module))) if within(m, CONSUMERS)} == set()


@pytest.mark.parametrize("module", [m for m in MODULES if layer(m) == "consumers"])
def test_the_consumers_never_reach_the_api(module: str) -> None:
    modules = own(imported_modules(source_of(module)))

    assert not {m for m in modules if within(m, API) or m in SHARED}


@pytest.mark.parametrize("module", [m for m in MODULES if within(m, PRESENTATION)])
def test_the_shared_presentation_imports_only_use_cases_and_models(module: str) -> None:
    modules = own(imported_modules(source_of(module)))

    assert {m for m in modules if not within(m, USECASES, MODELS, PRESENTATION)} == set()


@pytest.mark.parametrize(
    ("consumer", "other"),
    [(module, MCP) for module in MODULES if within(module, CLI)]
    + [(module, CLI) for module in MODULES if within(module, MCP)],
)
def test_the_cli_and_the_mcp_server_never_import_each_other(consumer: str, other: str) -> None:
    assert {m for m in own(imported_modules(source_of(consumer))) if within(m, other)} == set()


# --- the check itself -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("module", "source", "found"),
    [
        (
            f"{USECASES}.search_offers",
            "from deweloperuch_mcp.api.http import rsc_page",
            {f"{API}.http", f"{API}.http.rsc_page"},
        ),
        (
            f"{USECASES}.search_offers",
            "from deweloperuch_mcp.consumers.shared import offer_views",
            {f"{CONSUMERS}.shared", f"{CONSUMERS}.shared.offer_views"},
        ),
        (f"{USECASES}.search_offers", "from deweloperuch_mcp import bootstrap", {BOOTSTRAP}),
        (
            f"{USECASES}.search_offers",
            "def f():\n    import httpx",
            {"httpx"},
        ),
        (f"{MODELS}.offer", "import pydantic", {"pydantic"}),
        (f"{MODELS}.values", "import socket", {"socket"}),
        (f"{MODELS}.values", "import urllib.request", {"urllib.request"}),
        (f"{MODELS}.values", "from importlib import import_module", {"importlib"}),
        (f"{MODELS}.values", "import os", {"os"}),
        (f"{USECASES}.search_offers", "from pathlib import Path", {"pathlib"}),
        (f"{USECASES}.search_offers", "import subprocess", {"subprocess"}),
        (f"{MODELS}.offer", "from deweloperuch_mcp import errors", {f"{PACKAGE}.errors"}),
        (f"{MODELS}.offer", "from deweloperuch_mcp.throttle import x", {f"{PACKAGE}.throttle"}),
        (f"{MODELS}.offer", "from deweloperuch_mcp.usecases.ports import Clock", {PORTS}),
        (f"{MODELS}.offer", "from deweloperuch_mcp.api import links", {API, f"{API}.links"}),
        (
            f"{API}.adapters.offers_api",
            "from deweloperuch_mcp.usecases.search_offers import SearchOffers",
            {f"{USECASES}.search_offers"},
        ),
        (
            f"{API}.adapters.offers_api",
            "from deweloperuch_mcp.usecases.support import arguments",
            {f"{USECASES}.support", f"{USECASES}.support.arguments"},
        ),
        (
            f"{API}.adapters.offers_api",
            "from deweloperuch_mcp.consumers.shared import offer_views",
            {f"{CONSUMERS}.shared", f"{CONSUMERS}.shared.offer_views"},
        ),
        (f"{API}.adapters.offers_api", "from deweloperuch_mcp import bootstrap", {BOOTSTRAP}),
        (
            f"{CLI}.commands.offers_commands",
            "from deweloperuch_mcp.api.http import rsc_page",
            {f"{API}.http", f"{API}.http.rsc_page"},
        ),
        (
            f"{CONSUMERS}.mcp.server",
            "from deweloperuch_mcp import throttle",
            {f"{PACKAGE}.throttle"},
        ),
        (f"{CONSUMERS}.cli.app", "import httpx", {"httpx"}),
        (f"{PACKAGE}.cli", "import typer", {"typer"}),
        (BOOTSTRAP, "from deweloperuch_mcp import cli", {f"{PACKAGE}.cli"}),
        (BOOTSTRAP, "from deweloperuch_mcp.consumers import mcp", {CONSUMERS, f"{CONSUMERS}.mcp"}),
        (f"{PACKAGE}.throttle", "import httpx", {"httpx"}),
        (
            f"{PACKAGE}.cli",
            "from deweloperuch_mcp.api.http import transport",
            {f"{API}.http", f"{API}.http.transport"},
        ),
        (f"{PACKAGE}.mcp_server", "from deweloperuch_mcp import bootstrap", {BOOTSTRAP}),
        (
            f"{CLI}.commands.offers_commands",
            "from deweloperuch_mcp.consumers.mcp.support import calls",
            {f"{MCP}.support", f"{MCP}.support.calls"},
        ),
        (
            f"{MCP}.tools.search_offers_tool",
            "from deweloperuch_mcp.consumers.cli.support import common",
            {f"{CLI}.support", f"{CLI}.support.common"},
        ),
        (f"{MCP}.tools.search_offers_tool", "import typer", {"typer"}),
        (f"{CLI}.app", "from mcp.types import Tool", {"mcp.types"}),
        (f"{PRESENTATION}.offer_views", "from deweloperuch_mcp import bootstrap", {BOOTSTRAP}),
        (
            f"{PRESENTATION}.offer_views",
            "from deweloperuch_mcp.consumers.mcp.support import calls",
            {f"{MCP}.support", f"{MCP}.support.calls"},
        ),
        (f"{PRESENTATION}.offer_views", "import typer", {"typer"}),
        (
            f"{API}.adapters.offers_api",
            "from deweloperuch_mcp.consumers.shared.text import printable",
            {f"{PRESENTATION}.text"},
        ),
    ],
)
def test_the_check_catches_each_wrong_direction(module: str, source: str, found: set[str]) -> None:
    assert violations(module, source) == found


@pytest.mark.parametrize(
    ("module", "source"),
    [
        (f"{MODELS}.offer", "import re\nfrom deweloperuch_mcp.models.values import CitySlug"),
        (f"{MODELS}.offer", "from collections.abc import Mapping\nimport datetime as dt"),
        (f"{USECASES}.search_offers", "from contextlib import contextmanager"),
        (f"{USECASES}.search_offers", "from deweloperuch_mcp.usecases import ports"),
        (f"{USECASES}.search_offers", "from deweloperuch_mcp.models.offer import Offer"),
        (f"{API}.http.rsc_page", "import httpx\nfrom deweloperuch_mcp import flight"),
        (f"{API}.adapters.offers_api", "from deweloperuch_mcp.usecases.ports import OfferCatalog"),
        (f"{API}.adapters.offers_api", "from deweloperuch_mcp.usecases import ports"),
        (f"{API}.adapters.offers_api", "from deweloperuch_mcp.models.offer import Offer"),
        (BOOTSTRAP, "from deweloperuch_mcp.usecases.search_offers import SearchOffers"),
        (BOOTSTRAP, "from deweloperuch_mcp.api.http.transport import HttpClient"),
        (
            f"{CONSUMERS}.mcp.server",
            "import asyncio\nfrom mcp.server.mcpserver import MCPServer\n"
            "from deweloperuch_mcp.bootstrap import Session",
        ),
        (
            f"{CLI}.commands.offers_commands",
            "from deweloperuch_mcp.consumers.shared import offer_views",
        ),
        (f"{PACKAGE}.cli", "from deweloperuch_mcp.consumers.cli.app import main"),
        (
            f"{CLI}.commands.offers_commands",
            "import typer\nfrom deweloperuch_mcp.consumers.shared.view import View",
        ),
        (f"{MCP}.tools.get_offer_tool", "from deweloperuch_mcp.usecases.get_offer import X"),
        (f"{PRESENTATION}.offer_views", "from pydantic import BaseModel"),
    ],
)
def test_the_check_lets_the_right_direction_pass(module: str, source: str) -> None:
    assert violations(module, source) == set()


@pytest.mark.parametrize(
    ("source", "found"),
    [
        ("from deweloperuch_mcp.models import offer", {MODELS, f"{MODELS}.offer"}),
        ("from deweloperuch_mcp.usecases import ports", {USECASES, PORTS}),
        ("import deweloperuch_mcp.api", {API}),
        ("from deweloperuch_mcp import bootstrap", {PACKAGE, BOOTSTRAP}),
        (
            "from deweloperuch_mcp.consumers.shared import offer_views",
            {f"{CONSUMERS}.shared", f"{CONSUMERS}.shared.offer_views"},
        ),
        ("def f():\n    from deweloperuch_mcp.models.values import X", {f"{MODELS}.values"}),
    ],
)
def test_the_check_sees_every_way_to_import(source: str, found: set[str]) -> None:
    assert imported_modules(source) == found


# --- the models do not know the consumers' vocabulary (D13) ---------------------------------


@pytest.mark.parametrize("module", [m for m in MODULES if layer(m) == "models"])
def test_model_messages_name_no_tool_nor_parameter(module: str) -> None:
    said = [text for text in message_texts(source_of(module)) if INTERFACE_WORDS.search(text)]

    assert said == []


def test_the_vocabulary_check_sees_a_tool_in_a_message() -> None:
    source = (
        'def f():\n    """Doc of search_offers."""\n'
        '    raise E(f"Podaj city_slug z search_locations {x}.")'
    )

    assert message_texts(source) == ["Podaj city_slug z search_locations "]
    assert INTERFACE_WORDS.search(message_texts(source)[0])
