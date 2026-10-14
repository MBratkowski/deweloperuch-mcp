"""The package's modules as the D17 conventions test reads them (AST): their layer, folder,
classes and public functions.
"""

import ast
from dataclasses import dataclass

from support.paths import SRC

PACKAGE = "deweloperuch_mcp"


SOURCE = SRC / PACKAGE


def snake_to_pascal(name: str) -> str:
    return "".join(part.capitalize() for part in name.split("_"))


def tree_of(module: str) -> ast.Module:
    return ast.parse((SOURCE / f"{module}.py").read_text(encoding="utf-8"))


def classes(tree: ast.Module) -> dict[str, ast.ClassDef]:
    return {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}


@dataclass(frozen=True)
class Module:
    """One module of a layer, as the rules see it."""

    path: str
    """``api/adapters/offers_api``."""

    @property
    def folder(self) -> str:
        return self.path.rsplit("/", 1)[0]

    @property
    def base(self) -> str:
        return self.path.rsplit("/", 1)[1]

    @property
    def layer(self) -> str:
        return self.path.split("/", 1)[0]

    @property
    def main(self) -> str:
        """The class the module is named after: ``OffersApi``."""
        return snake_to_pascal(self.base)

    @property
    def tree(self) -> ast.Module:
        return tree_of(self.path)

    @property
    def classes(self) -> dict[str, ast.ClassDef]:
        return classes(self.tree)
