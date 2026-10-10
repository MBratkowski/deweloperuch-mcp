"""D6: the CLI and the MCP server are thin adapters over the domain services.

They import from the package only ``services``, ``errors`` and ``domain.models`` (the MCP
server also its representation, ``mcp_results``, which itself imports only
``domain.models``), never the client (``deweloperuch_mcp.client``) nor the transport
policy modules; everything else they import is outside the package. Checked on the
source (AST), since importing ``services`` loads the client anyway.
"""

import ast
from pathlib import Path

import pytest

PACKAGE = "deweloperuch_mcp"
SOURCE = Path(__file__).resolve().parent.parent / "src" / PACKAGE
CORE = {f"{PACKAGE}.services", f"{PACKAGE}.errors", f"{PACKAGE}.domain.models"}
ALLOWED = {
    "cli.py": CORE,
    "mcp_server.py": CORE | {f"{PACKAGE}.mcp_results"},
    "mcp_results.py": {f"{PACKAGE}.domain.models"},
}


def imported_modules(source: str) -> set[str]:
    """Every module a source imports, anywhere in it; ``from a import b`` counts as
    ``a.b`` when ``b`` is a module of the package (``from deweloperuch_mcp import services``)."""
    modules: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, "relative imports hide what is imported"
            assert node.module is not None
            modules.add(node.module)
            if node.module == PACKAGE:
                modules.update(f"{PACKAGE}.{alias.name}" for alias in node.names)
    return modules


@pytest.mark.parametrize("adapter", ALLOWED)
def test_adapters_import_only_services_errors_and_domain_models(adapter: str) -> None:
    modules = imported_modules((SOURCE / adapter).read_text(encoding="utf-8"))

    own = {module for module in modules if module.split(".")[0] == PACKAGE} - {PACKAGE}
    assert own <= ALLOWED[adapter]
    assert not any(module.startswith(f"{PACKAGE}.client") for module in modules)


@pytest.mark.parametrize("adapter", ["cli.py", "mcp_server.py"])
def test_adapters_call_the_services(adapter: str) -> None:
    modules = imported_modules((SOURCE / adapter).read_text(encoding="utf-8"))

    assert f"{PACKAGE}.services" in modules


@pytest.mark.parametrize(
    ("source", "found"),
    [
        ("from deweloperuch_mcp.client import transport", {"deweloperuch_mcp.client"}),
        ("import deweloperuch_mcp.client.rsc", {"deweloperuch_mcp.client.rsc"}),
        (
            "from deweloperuch_mcp import client",
            {"deweloperuch_mcp", "deweloperuch_mcp.client"},
        ),
        ("def f():\n    from deweloperuch_mcp.client import dto", {"deweloperuch_mcp.client"}),
    ],
)
def test_the_check_sees_every_way_to_import_the_client(source: str, found: set[str]) -> None:
    assert imported_modules(source) == found
