"""D13: the direction of dependencies between the layers, checked on the source (AST).

    interfaces  ->  application  ->  domain
    bootstrap   ->  application, infrastructure, domain
    infrastructure  ->  domain

- ``domain``: the standard library and ``domain`` only (no pydantic, no I/O libraries,
  nothing of the rest of the package);
- ``application``: the standard library, ``domain`` and ``application``;
- ``infrastructure``: ``domain``, ``infrastructure``, the stdlib modules shared with
  ``recon/`` (``SHARED``) and third-party libraries; never ``application``, the composition
  root or the interfaces;
- ``bootstrap``: anything below the interfaces;
- the stdlib modules shared with ``recon/``: only each other (tests/test_recon_config.py
  checks they stay stdlib-only);
- ``interfaces`` (the CLI and the MCP server): ``application``, ``domain``,
  ``bootstrap``, ``interfaces`` and their libraries (``INTERFACE_LIBRARIES``); never the
  infrastructure nor the modules shared with ``recon/`` (the composition root hands
  them over);
- the entry points of ``[project.scripts]`` (``cli``, ``mcp_server``) are shims: only
  the interfaces; the ``errors`` module re-exports the domain's errors and the
  interfaces' ``printable``.

Checked on the source, since importing a module loads what it imports anyway. Every
module of the package must belong to a layer (``test_every_module_has_a_layer``).
"""

import ast
import re
import sys
from pathlib import Path

import pytest

PACKAGE = "deweloperuch_mcp"
SOURCE = Path(__file__).resolve().parent.parent / "src" / PACKAGE

SHARED = frozenset(
    f"{PACKAGE}.{name}"
    for name in ("identity", "throttle", "http_policy", "retry_after", "allowlist", "flight")
)
"""Stdlib-only modules ``recon/`` imports at these paths."""

DOMAIN_STDLIB = frozenset(
    {"re", "dataclasses", "enum", "typing", "collections.abc", "datetime", "math", "itertools"}
    | {"functools"}
)
"""The standard library the domain may use: values, types and arithmetic; no I/O, no
processes, no network, no files, no dynamic imports. Add a module only with a reason."""

APPLICATION_STDLIB = DOMAIN_STDLIB | {"contextlib"}
"""The use cases also scope the wording of failures (``contextlib.contextmanager``)."""

DOMAIN, APPLICATION, INFRASTRUCTURE = (
    f"{PACKAGE}.domain",
    f"{PACKAGE}.application",
    f"{PACKAGE}.infrastructure",
)
BOOTSTRAP = f"{PACKAGE}.bootstrap"
INTERFACES = f"{PACKAGE}.interfaces"
SHIMS = frozenset({f"{PACKAGE}.cli", f"{PACKAGE}.mcp_server"})
"""The modules ``[project.scripts]`` names: they only hand over to the interfaces."""
INTERFACE_LIBRARIES = frozenset({"mcp", "typer", "pydantic"})
"""The third-party libraries the interfaces build on."""


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
    for prefix, name in (
        (DOMAIN, "domain"),
        (APPLICATION, "application"),
        (INFRASTRUCTURE, "infrastructure"),
    ):
        if within(module, prefix):
            return name
    if module in SHARED:
        return "shared"
    if module == BOOTSTRAP:
        return "bootstrap"
    if within(module, INTERFACES):
        return "interfaces"
    if module in SHIMS:
        return "shim"
    if module == f"{PACKAGE}.errors":
        return "errors"
    if module == PACKAGE:
        return "package"
    return "?"


def violations(module: str, source: str) -> set[str]:
    """What ``module`` (whose code is ``source``) imports against its layer's rule."""
    modules = imported_modules(source)
    mine = own(modules)
    others = modules - mine - {PACKAGE}
    match layer(module):
        case "domain":
            return {m for m in mine if not within(m, DOMAIN)} | (others - DOMAIN_STDLIB)
        case "application":
            allowed = (DOMAIN, APPLICATION)
            bad = {m for m in mine if not within(m, *allowed)}
            return bad | (others - APPLICATION_STDLIB)
        case "infrastructure":
            return {m for m in mine if not (within(m, DOMAIN, INFRASTRUCTURE) or m in SHARED)}
        case "bootstrap":
            return {
                m
                for m in mine
                if not (within(m, DOMAIN, APPLICATION, INFRASTRUCTURE) or m in SHARED)
            }
        case "shared":
            return {m for m in mine if m not in SHARED} | {m for m in others if not stdlib(m)}
        case "errors":
            return mine - {f"{DOMAIN}.errors", f"{INTERFACES}.text"} | others
        case "interfaces":
            bad = {m for m in mine if not within(m, APPLICATION, DOMAIN, BOOTSTRAP, INTERFACES)}
            return bad | {
                m for m in others if not stdlib(m) and m.split(".")[0] not in INTERFACE_LIBRARIES
            }
        case "shim":
            return {m for m in mine if not within(m, INTERFACES)} | others
        case "package":
            return modules
    raise AssertionError(f"{module}: moduł bez warstwy")


MODULES = sorted(module_name(path) for path in SOURCE.rglob("*.py"))


def source_of(module: str) -> str:
    path = SOURCE.parent.joinpath(*module.split("."))
    file = path / "__init__.py" if path.is_dir() else path.with_suffix(".py")
    return file.read_text(encoding="utf-8")


def test_every_module_has_a_layer() -> None:
    assert {module: layer(module) for module in MODULES if layer(module) == "?"} == {}
    assert {"domain", "application", "infrastructure", "bootstrap", "shared"} <= {
        layer(module) for module in MODULES
    }


@pytest.mark.parametrize("module", MODULES)
def test_each_module_imports_only_what_its_layer_may(module: str) -> None:
    assert violations(module, source_of(module)) == set()


@pytest.mark.parametrize("module", [m for m in MODULES if layer(m) == "infrastructure"])
def test_the_infrastructure_imports_nothing_above_it(module: str) -> None:
    """The client knows the service and the domain it maps to, nothing above them: not
    the use cases, the composition root nor the interfaces."""
    above = (APPLICATION, BOOTSTRAP, INTERFACES, *SHIMS)
    assert {m for m in own(imported_modules(source_of(module))) if within(m, *above)} == set()


@pytest.mark.parametrize(
    ("shim", "interface"),
    [
        (f"{PACKAGE}.cli", f"{INTERFACES}.cli.app"),
        (f"{PACKAGE}.mcp_server", f"{INTERFACES}.mcp.server"),
    ],
)
def test_the_entry_points_only_hand_over_to_the_interfaces(shim: str, interface: str) -> None:
    assert own(imported_modules(source_of(shim))) == {interface}


@pytest.mark.parametrize("module", [m for m in MODULES if layer(m) == "interfaces"])
def test_the_interfaces_never_reach_the_infrastructure(module: str) -> None:
    modules = own(imported_modules(source_of(module)))

    assert not {m for m in modules if within(m, INFRASTRUCTURE) or m in SHARED}


# --- the check itself -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("module", "source", "found"),
    [
        (
            f"{APPLICATION}.offers",
            "from deweloperuch_mcp.infrastructure.deweloperuch import rsc",
            {f"{INFRASTRUCTURE}.deweloperuch", f"{INFRASTRUCTURE}.deweloperuch.rsc"},
        ),
        (
            f"{APPLICATION}.offers",
            "def f():\n    import httpx",
            {"httpx"},
        ),
        (f"{DOMAIN}.offers", "import pydantic", {"pydantic"}),
        (f"{DOMAIN}.values", "import socket", {"socket"}),
        (f"{DOMAIN}.values", "import urllib.request", {"urllib.request"}),
        (f"{DOMAIN}.values", "from importlib import import_module", {"importlib"}),
        (f"{DOMAIN}.values", "import os", {"os"}),
        (f"{APPLICATION}.offers", "from pathlib import Path", {"pathlib"}),
        (f"{APPLICATION}.offers", "import subprocess", {"subprocess"}),
        (f"{DOMAIN}.offers", "from deweloperuch_mcp import errors", {f"{PACKAGE}.errors"}),
        (f"{DOMAIN}.offers", "from deweloperuch_mcp.throttle import x", {f"{PACKAGE}.throttle"}),
        (
            f"{INFRASTRUCTURE}.deweloperuch.offers",
            "from deweloperuch_mcp.application.offers import SearchOffers",
            {f"{APPLICATION}.offers"},
        ),
        (
            f"{INFRASTRUCTURE}.deweloperuch.offers",
            "from deweloperuch_mcp.interfaces import views",
            {INTERFACES, f"{INTERFACES}.views"},
        ),
        (
            f"{INTERFACES}.cli.offers",
            "from deweloperuch_mcp.infrastructure.deweloperuch import rsc",
            {f"{INFRASTRUCTURE}.deweloperuch", f"{INFRASTRUCTURE}.deweloperuch.rsc"},
        ),
        (
            f"{INTERFACES}.mcp.server",
            "from deweloperuch_mcp import throttle",
            {f"{PACKAGE}.throttle"},
        ),
        (f"{INTERFACES}.cli.app", "import httpx", {"httpx"}),
        (f"{PACKAGE}.cli", "import typer", {"typer"}),
        (BOOTSTRAP, "from deweloperuch_mcp import cli", {f"{PACKAGE}.cli"}),
        (f"{PACKAGE}.throttle", "import httpx", {"httpx"}),
        (
            f"{PACKAGE}.cli",
            "from deweloperuch_mcp.infrastructure.deweloperuch import transport",
            {
                f"{INFRASTRUCTURE}.deweloperuch",
                f"{INFRASTRUCTURE}.deweloperuch.transport",
            },
        ),
        (f"{PACKAGE}.mcp_server", "from deweloperuch_mcp import bootstrap", {BOOTSTRAP}),
    ],
)
def test_the_check_catches_each_wrong_direction(module: str, source: str, found: set[str]) -> None:
    assert violations(module, source) == found


@pytest.mark.parametrize(
    ("module", "source"),
    [
        (f"{DOMAIN}.offers", "import re\nfrom deweloperuch_mcp.domain.values import CitySlug"),
        (f"{DOMAIN}.offers", "from collections.abc import Mapping\nimport datetime as dt"),
        (f"{APPLICATION}.offers", "from contextlib import contextmanager"),
        (f"{APPLICATION}.offers", "from deweloperuch_mcp.domain import ports"),
        (f"{INFRASTRUCTURE}.deweloperuch.rsc", "import httpx\nfrom deweloperuch_mcp import flight"),
        (BOOTSTRAP, "from deweloperuch_mcp.application.offers import SearchOffers"),
        (
            f"{INTERFACES}.mcp.server",
            "import asyncio\nfrom mcp.server.mcpserver import MCPServer\n"
            "from deweloperuch_mcp.bootstrap import Session",
        ),
        (f"{PACKAGE}.cli", "from deweloperuch_mcp.interfaces.cli.app import main"),
    ],
)
def test_the_check_lets_the_right_direction_pass(module: str, source: str) -> None:
    assert violations(module, source) == set()


@pytest.mark.parametrize(
    ("source", "found"),
    [
        ("from deweloperuch_mcp.domain import offers", {DOMAIN, f"{DOMAIN}.offers"}),
        ("import deweloperuch_mcp.infrastructure", {INFRASTRUCTURE}),
        ("from deweloperuch_mcp import bootstrap", {PACKAGE, BOOTSTRAP}),
        ("from deweloperuch_mcp.interfaces import views", {INTERFACES, f"{INTERFACES}.views"}),
        ("def f():\n    from deweloperuch_mcp.domain.values import X", {f"{DOMAIN}.values"}),
    ],
)
def test_the_check_sees_every_way_to_import(source: str, found: set[str]) -> None:
    assert imported_modules(source) == found


# --- the domain does not know the interfaces' vocabulary (D13) --------------------------------

INTERFACE_WORDS = re.compile(
    r"search_locations|search_offers|get_offer|get_investment|get_government_statistics|"
    r"\b(price_min|price_max|area_min|area_max|per_page|investment_slug|offer_id|"
    r"include_history|periods|query|city|location|dataset|sort|page|limit)\b"
)
"""MCP tools and the parameters of the CLI and the MCP server (``application.arguments``)."""


def message_texts(source: str) -> list[str]:
    """The string literals of a module that are not documentation (docstrings and the
    bare strings documenting attributes): what it may say."""
    tree = ast.parse(source)
    docstrings = {
        id(node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    }
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
        and " " in node.value  # a phrase, not an identifier or a value such as "city"
    ]


@pytest.mark.parametrize("module", [m for m in MODULES if layer(m) == "domain"])
def test_domain_messages_name_no_tool_nor_parameter(module: str) -> None:
    said = [text for text in message_texts(source_of(module)) if INTERFACE_WORDS.search(text)]

    assert said == []


def test_the_vocabulary_check_sees_a_tool_in_a_message() -> None:
    source = (
        'def f():\n    """Doc of search_offers."""\n'
        '    raise E(f"Podaj city_slug z search_locations {x}.")'
    )

    assert message_texts(source) == ["Podaj city_slug z search_locations "]
    assert INTERFACE_WORDS.search(message_texts(source)[0])
