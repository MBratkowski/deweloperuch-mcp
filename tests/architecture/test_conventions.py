"""D17: one code pattern per layer, checked on the source (AST).

Every module of ``models``, ``usecases``, ``api`` and ``consumers`` follows these rules,
without exceptions (the migration's allowlist is gone): any break fails
``test_every_module_follows_d17``.

- **Functions**: no public module-level functions in ``models``, ``usecases``, ``api``.
- **Names**: no module basename in two places; a role module is named after its main class
  (``models/price_history.py`` -> ``PriceHistory``, ``api/adapters/offers_api.py`` ->
  ``OffersApi``...); a view never has a model's name; views live in ``*_views.py``.
- **Folders**: role folders (``ROLE_FOLDERS``) hold only modules of their role; the top of
  a layer holds only what ``TOP_LEVEL`` names; ``models`` is flat.
- **Support is capability-agnostic** (``SUPPORT_FOLDERS``): no role classes, no imports of
  one operation's code (use cases, tools, presenters, commands, adapters, DTOs, queries),
  no views or capability models in the consumers' support, no formatters (``format_*``),
  result models (``*Result``) or presenter functions there. One exception, by name
  (``FAMILY_SUPPORT``): ``usecases/support`` may hold logic that several operations of
  one capability family share (``InvestmentLookup`` for ``GetOffer`` and
  ``GetInvestment``), and only there may support import a capability model.
- **Shapes**: models are frozen dataclasses, enums or errors; a use case module has
  ``<Op>`` (public method ``execute`` only), ``<Op>Request`` (a frozen dataclass with a
  classmethod ``parse``) and ``<Op>Result`` (a frozen dataclass); a DTO module's main
  class has ``to_model()``; an MCP tool is a ``*Tool(ToolBase)`` with ``async __call__``
  in ``consumers/mcp/tools``; ``typing.Protocol`` classes live in ``usecases/ports.py``.
"""

import ast
import re
from collections import Counter

import pytest

from support.checks import conventions
from support.checks.conventions import PACKAGE, SOURCE, Module, classes, tree_of

LAYERS = ("models", "usecases", "api", "consumers")

ROLE_FOLDERS = {
    "api/adapters": "_api",
    "api/dto": "_dto",
    "api/queries": "_query",
    "consumers/mcp/tools": "_tool",
    "consumers/mcp/presenters": "_mcp_presenter",
    "consumers/cli/presenters": "_cli_presenter",
    "consumers/cli/commands": "_commands",
}
"""Each role folder and the suffix of its modules (and of their main classes; command
modules hold Typer functions, no class). ``api/dto/dto.py`` is the DTOs' base."""
ROLE_CLASSES = ("Api", "Dto", "Query", "Tool", "Presenter")
SUPPORT_FOLDERS = (
    "api/http",
    "usecases/support",
    "consumers/mcp/support",
    "consumers/cli/support",
)
TOP_LEVEL = {
    "api": {"links"},
    "consumers": set(),
    "consumers/mcp": {"server"},
    "consumers/cli": {"app"},
}
"""The modules a layer's top folder may hold besides its folders (``usecases``: the
operations and ``ports``; ``models``: the concepts)."""
PLUMBING = {"models/values", "models/errors", "usecases/ports", "api/links"}
"""Shared plumbing with a descriptive name (no main class to match)."""
SHARED_SUPPORT = {"consumers/shared/view", "consumers/shared/text", "consumers/shared/choices"}
"""What both consumers present that belongs to no capability."""
FAMILY_SUPPORT = {"usecases/support/investment_lookup": {"InvestmentLookup"}}
"""``usecases/support`` modules that several operations of one capability family share,
with the classes each may hold; nothing else in support imports a capability model."""
OPERATION_CODE = (
    f"{PACKAGE}.consumers.mcp.tools",
    f"{PACKAGE}.consumers.mcp.presenters",
    f"{PACKAGE}.consumers.cli.presenters",
    f"{PACKAGE}.consumers.cli.commands",
    f"{PACKAGE}.api.adapters",
    f"{PACKAGE}.api.queries",
)
"""Packages whose modules belong to one operation (with the use cases, the DTOs and the
consumers' views)."""


MODULES = sorted(
    str(path.relative_to(SOURCE).with_suffix(""))
    for layer in LAYERS
    for path in (SOURCE / layer).rglob("*.py")
    if path.name != "__init__.py"
)
BASENAMES = Counter(module.rsplit("/", 1)[1] for module in MODULES)


def public_functions(tree: ast.Module) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    return [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        and not node.name.startswith("_")
    ]


def methods(cls: ast.ClassDef) -> dict[str, ast.FunctionDef | ast.AsyncFunctionDef]:
    return {
        node.name: node
        for node in cls.body
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
    }


def base_names(cls: ast.ClassDef) -> set[str]:
    return {ast.unparse(base).split("[")[0].rsplit(".", 1)[-1] for base in cls.bases}


def frozen_dataclass(cls: ast.ClassDef) -> bool:
    return any(
        isinstance(dec, ast.Call)
        and ast.unparse(dec.func).endswith("dataclass")
        and any(k.arg == "frozen" and ast.unparse(k.value) == "True" for k in dec.keywords)
        for dec in cls.decorator_list
    )


def classmethod_named(cls: ast.ClassDef, name: str) -> bool:
    found = methods(cls).get(name)
    return found is not None and any(ast.unparse(d) == "classmethod" for d in found.decorator_list)


def imported_names(tree: ast.Module) -> list[tuple[str, str]]:
    """``(module, name)`` of every ``from module import name`` of the package."""
    return [
        (node.module or "", alias.name)
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(PACKAGE)
        for alias in node.names
    ]


def operation_module(module: str) -> bool:
    """A module of one operation: a use case, a tool, a presenter, a command group, an
    adapter, a DTO, a query, or the consumers' views of a capability."""
    path = module.removeprefix(f"{PACKAGE}.").replace(".", "/")
    folder = path.rsplit("/", 1)[0]
    return (
        module.startswith(OPERATION_CODE)
        or (folder == "usecases" and path != "usecases/ports")
        or (folder == "api/dto" and path != "api/dto/dto")
        or (folder == "consumers/shared" and path not in SHARED_SUPPORT)
    )


MODEL_CLASSES = {
    name for module in MODULES if module.startswith("models/") for name in classes(tree_of(module))
}
DTO_BASES = {
    name
    for module in MODULES
    if module.startswith("api/dto/")
    for cls in classes(tree_of(module)).values()
    for name in base_names(cls)
}
"""Classes other DTOs extend (a base needs no ``to_model`` of its own)."""


def functions_rule(module: Module) -> list[str]:
    if module.layer not in ("models", "usecases", "api"):
        return []
    return [f"public function {f.name}()" for f in public_functions(module.tree)]


def names_rule(module: Module) -> list[str]:
    said = []
    if BASENAMES[module.base] > 1:
        said.append(f"basename {module.base!r} is used by another module")
    named_after_class = module.folder in ("models", "usecases") or (
        module.folder in ROLE_FOLDERS and module.folder != "consumers/cli/commands"
    )
    if named_after_class and module.path not in PLUMBING and module.main not in module.classes:
        said.append(f"no class {module.main} (a module is named after its main class)")
    return said


def folders_rule(module: Module) -> list[str]:
    folder, base, said = module.folder, module.base, []
    if folder in ROLE_FOLDERS and not base.endswith(ROLE_FOLDERS[folder]) and base != "dto":
        said.append(f"{folder}/ holds only *{ROLE_FOLDERS[folder]}.py modules")
    if folder in TOP_LEVEL and base not in TOP_LEVEL[folder]:
        said.append(f"{folder}/ holds only {sorted(TOP_LEVEL[folder])} besides its folders")
    if module.layer == "models" and folder != "models":
        said.append("models/ is flat")
    return said


def support_rule(module: Module) -> list[str]:
    """Support code serves every capability and belongs to none."""
    folder, said = module.folder, []
    if folder not in SUPPORT_FOLDERS:
        return []
    for name, cls in module.classes.items():
        if name.endswith(ROLE_CLASSES) or "execute" in methods(cls):
            said.append(f"role class {name} in support")
    family = FAMILY_SUPPORT.get(module.path)
    if family is not None and set(module.classes) != family:
        said.append(f"family support holds {sorted(module.classes)}, not {sorted(family)}")
    for source, name in imported_names(module.tree):
        concept = source.startswith(f"{PACKAGE}.models.") and source.rsplit(".", 1)[1] not in (
            "values",
            "errors",
        )
        if operation_module(source) or (concept and family is None):
            said.append(f"imports {name} from {source.removeprefix(PACKAGE + '.')}")
    for f in public_functions(module.tree):
        if f.name.startswith("format_"):
            said.append(f"formatter {f.name}() (belongs to its command's presenter)")
    if folder == "consumers/mcp/support":
        said += [f"result model {name}" for name in module.classes if name.endswith("Result")]
    return said


def views_rule(module: Module) -> list[str]:
    if module.folder != "consumers/shared" or module.path in SHARED_SUPPORT:
        return []
    said = []
    if not module.base.endswith("_views"):
        said.append("views live in <capability>_views.py")
    said += [f"view {name} has a model's name" for name in module.classes if name in MODEL_CLASSES]
    said += [
        f"view builder {f.name}() (use a from_result classmethod)"
        for f in public_functions(module.tree)
    ]
    return said


def models_rule(module: Module) -> list[str]:
    if module.folder != "models" or module.path in PLUMBING:
        return []
    return [
        f"class {name} is no frozen dataclass, enum or error"
        for name, cls in module.classes.items()
        if not name.startswith("_")
        and not frozen_dataclass(cls)
        and not any(b.endswith(("Enum", "Error", "Exception")) for b in base_names(cls))
    ]


def use_cases_rule(module: Module) -> list[str]:
    if module.folder != "usecases" or module.path in PLUMBING:
        return []
    main, found, said = module.main, module.classes, []
    if main in found:
        public = sorted(m for m in methods(found[main]) if not m.startswith("_"))
        if public != ["execute"]:
            said.append(f"{main}'s public methods are {public}, not ['execute']")
    request, result = found.get(f"{main}Request"), found.get(f"{main}Result")
    if request is None or not classmethod_named(request, "parse"):
        said.append(f"no {main}Request with a classmethod parse()")
    if request is not None and not frozen_dataclass(request):
        said.append(f"{main}Request is no frozen dataclass")
    if result is None:
        said.append(f"no {main}Result")
    elif not frozen_dataclass(result):
        said.append(f"{main}Result is no frozen dataclass")
    return said


def api_rule(module: Module) -> list[str]:
    if module.layer != "api":
        return []
    main, found = module.main, module.classes
    if module.folder == "api/dto":
        dto = found.get(main)
        if dto is not None and main not in DTO_BASES and "to_model" not in methods(dto):
            return [f"{main} has no to_model()"]
        return []
    return [f"DTO {name} outside api/dto/" for name in found if name.endswith("Dto")]


def tools_rule(module: Module) -> list[str]:
    if module.folder == "consumers/mcp/tools":
        tool = module.classes.get(module.main)
        if tool is None or "ToolBase" not in base_names(tool):
            return [f"no {module.main}(ToolBase)"]
        if not isinstance(methods(tool).get("__call__"), ast.AsyncFunctionDef):
            return [f"{module.main} has no async __call__"]
        return []
    if not module.path.startswith("consumers/mcp/"):
        return []
    functions = [  # a tool function: async, with the session's context as a parameter
        f.name
        for f in public_functions(module.tree)
        if isinstance(f, ast.AsyncFunctionDef)
        and any(
            arg.annotation is not None and "SessionContext" in ast.unparse(arg.annotation)
            for arg in f.args.args
        )
    ]
    tools = [name for name in module.classes if name.endswith("Tool") and name[0] != "_"]
    return [f"tool {name} outside consumers/mcp/tools/" for name in functions + tools]


def protocols_rule(module: Module) -> list[str]:
    if module.path == "usecases/ports":
        return []
    return [
        f"Protocol {name} outside usecases/ports.py"
        for name, cls in module.classes.items()
        if "Protocol" in base_names(cls)
    ]


RULES = (
    functions_rule,
    names_rule,
    folders_rule,
    support_rule,
    views_rule,
    models_rule,
    use_cases_rule,
    api_rule,
    tools_rule,
    protocols_rule,
)


def problems(path: str) -> set[str]:
    """Every rule of D17 that the module at ``path`` (``api/adapters/offers_api``) breaks."""
    module = Module(path)
    return {said for rule in RULES for said in rule(module)}


@pytest.mark.parametrize("module", MODULES)
def test_every_module_follows_d17(module: str) -> None:
    assert problems(module) == set()


def test_the_offers_reference_exists_in_every_layer() -> None:
    """The reference implementation of D17 (offers) exists in every layer."""
    reference = {
        "models/offer",
        "models/price_history",
        "usecases/search_offers",
        "usecases/get_offer",
        "usecases/support/investment_lookup",
        "api/adapters/offers_api",
        "api/adapters/investments_api",
        "api/dto/offers_page_dto",
        "api/dto/sale_events_dto",
        "api/dto/sale_dto",
        "api/dto/investment_dto",
        "api/dto/investment_sale_events_dto",
        "api/dto/developer_dto",
        "api/queries/offers_query",
        "api/http/rsc_page",
        "api/http/json_endpoint",
        "consumers/mcp/tools/search_offers_tool",
        "consumers/mcp/tools/get_offer_tool",
        "consumers/mcp/presenters/search_offers_mcp_presenter",
        "consumers/mcp/presenters/get_offer_mcp_presenter",
        "consumers/cli/commands/offers_commands",
        "consumers/cli/presenters/offer_cli_presenter",
        "consumers/cli/presenters/search_offers_cli_presenter",
        "consumers/cli/presenters/get_offer_cli_presenter",
        "consumers/shared/offer_views",
    }
    assert reference <= set(MODULES)


# --- the check itself -----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("module", "source", "found"),
    [
        ("models/offer", "def helper():\n    pass", "public function helper"),
        ("models/offer", "class Offer:\n    pass", "no frozen dataclass"),
        ("usecases/search_offers", "class SearchOffers:\n    def __call__(self): ...", "public"),
        ("usecases/search_offers", "class SearchOffers:\n    def execute(self): ...", "parse"),
        (
            "usecases/search_offers",
            "class SearchOffersRequest:\n    def parse(cls): ...",
            "classmethod parse",
        ),
        ("api/dto/offers_page_dto", "class OffersPageDto:\n    pass", "to_model"),
        ("api/adapters/offers_api", "class OffersApi:\n    pass\nclass XDto:\n    pass", "DTO"),
        ("consumers/mcp/support/calls", "class SearchOffersTool:\n    pass", "tool"),
        ("consumers/mcp/support/calls", "class GetOfferMcpPresenter:\n    pass", "role class"),
        ("consumers/mcp/tools/get_offer_tool", "class GetOfferTool:\n    pass", "ToolBase"),
        ("consumers/cli/support/common", "def format_offer(x):\n    pass", "formatter"),
        (
            "consumers/cli/support/common",
            "from deweloperuch_mcp.consumers.shared.offer_views import OfferDetailView",
            "imports OfferDetailView",
        ),
        (
            "consumers/cli/support/common",
            "from deweloperuch_mcp.models.offer import Offer",
            "imports Offer",
        ),
        (
            "usecases/support/failures",
            "from deweloperuch_mcp.usecases.get_offer import GetOfferResult",
            "imports GetOfferResult",
        ),
        (
            "usecases/support/failures",
            "from deweloperuch_mcp.models.investment import Investment",
            "imports Investment",
        ),
        (
            "usecases/support/investment_lookup",
            "class InvestmentLookup:\n    pass\nclass OfferLookup:\n    pass",
            "family support holds",
        ),
        ("consumers/shared/offer_views", "class Offer:\n    pass", "model's name"),
        ("consumers/shared/offer_views", "def offer_search(found):\n    pass", "view builder"),
        ("api/http/transport", "class Catalog(Protocol):\n    pass", "Protocol"),
    ],
)
def test_the_check_sees_a_broken_rule(
    module: str, source: str, found: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    def tree(_: str) -> ast.Module:
        return ast.parse(source)

    monkeypatch.setitem(globals(), "tree_of", tree)
    monkeypatch.setattr(conventions, "tree_of", tree)  # ``Module.tree`` reads it there

    assert any(re.search(found, said) for said in problems(module))
