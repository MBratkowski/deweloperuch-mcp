"""What the layering test knows about the package: its source, the stdlib modules the
models may import, and the texts of a module's messages.
"""

import ast
import re

from support.paths import SRC

PACKAGE = "deweloperuch_mcp"


SOURCE = SRC / PACKAGE


MODELS_STDLIB = frozenset(
    {"re", "dataclasses", "enum", "typing", "collections.abc", "datetime", "math", "itertools"}
    | {"functools"}
)
"""The standard library the models may use: values, types and arithmetic; no I/O, no
processes, no network, no files, no dynamic imports. Add a module only with a reason."""


def source_of(module: str) -> str:
    path = SOURCE.parent.joinpath(*module.split("."))
    file = path / "__init__.py" if path.is_dir() else path.with_suffix(".py")
    return file.read_text(encoding="utf-8")


INTERFACE_WORDS = re.compile(
    r"search_locations|search_offers|get_offer|get_investment|get_government_statistics|"
    r"\b(price_min|price_max|area_min|area_max|per_page|investment_slug|offer_id|"
    r"include_history|periods|query|city|location|dataset|sort|page|limit)\b"
)
"""MCP tools and the parameters of the CLI and the MCP server (``usecases.support.arguments``)."""


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
