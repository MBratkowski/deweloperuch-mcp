"""The layout of the tests themselves (AST, no imports of the modules checked).

- ``tests/support`` is test infrastructure (fakes, providers, builders, checks, the golden
  cases, the live harness, workers): no tests there, and it never imports a test module.
- Test modules hold tests: no helper classes, test code imported only from ``support``,
  no helper defined twice (identical) in two modules.
- Unit tests mirror the package: ``src/deweloperuch_mcp/<path>/<name>.py`` has its unit
  tests in ``tests/unit/<path>/test_<name>.py``; a unit test module without its source
  module fails, a source module without unit tests is only listed (a warning).
- Every module of ``support`` that defines fixtures is a plugin of tests/conftest.py.
"""

import ast
import warnings
from pathlib import Path

import pytest

from support.paths import PACKAGE_SOURCE, TESTS

SUPPORT = TESTS / "support"
UNIT = TESTS / "unit"
DATA = {"fixtures", "golden", "snapshots", "__pycache__"}
"""Folders of data, not code."""
TEST_PACKAGES = {
    path.name
    for path in TESTS.iterdir()
    if path.is_dir() and (path / "__init__.py").exists() and path.name != "support"
}
INSPECTS = {("safeguards/test_e2e_gate.py", "e2e")}
"""Test modules that import other test modules to inspect them (the live suite's marks)."""


def python_files(root: Path) -> list[Path]:
    return sorted(
        path for path in root.rglob("*.py") if not DATA & set(path.relative_to(TESTS).parts)
    )


def modules_of_tests() -> list[Path]:
    return [
        path
        for path in python_files(TESTS)
        if path.name.startswith("test_") and SUPPORT not in path.parents
    ]


def tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def imported(module: ast.Module) -> set[str]:
    """Top-level names of every module imported anywhere in ``module``."""
    found: set[str] = set()
    for node in ast.walk(module):
        if isinstance(node, ast.Import):
            found |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.add(node.module.split(".")[0])
    return found


def is_test_code(name: str) -> bool:
    return name in TEST_PACKAGES or name.startswith("test_") or name == "conftest"


def name_of(path: Path) -> str:
    return str(path.relative_to(TESTS))


def test_the_test_packages_are_found() -> None:
    assert {"unit", "contract", "integration", "characterization", "e2e"} <= TEST_PACKAGES


def test_support_has_no_tests_and_imports_no_test_module() -> None:
    problems = []
    for path in python_files(SUPPORT):
        module = tree(path)
        for node in module.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith(
                "test_"
            ):
                problems.append(f"{name_of(path)}: test {node.name}")
            if isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
                problems.append(f"{name_of(path)}: test class {node.name}")
        problems += [
            f"{name_of(path)} imports {name}" for name in imported(module) if is_test_code(name)
        ]

    assert problems == []


def test_test_modules_import_test_code_only_from_support() -> None:
    problems = [
        f"{name_of(path)} imports {name}"
        for path in [*modules_of_tests(), *TESTS.rglob("conftest.py")]
        for name in imported(tree(path))
        if is_test_code(name) and (name_of(path), name) not in INSPECTS
    ]

    assert problems == []


def test_test_modules_define_no_helper_classes() -> None:
    problems = [
        f"{name_of(path)}: {node.name}"
        for path in modules_of_tests()
        for node in tree(path).body
        if isinstance(node, ast.ClassDef) and not node.name.startswith("Test")
    ]

    assert problems == [], "fakes and runners belong in tests/support"


def test_no_helper_is_defined_twice() -> None:
    seen: dict[str, str] = {}
    problems = []
    for path in modules_of_tests():
        for node in tree(path).body:
            if isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef)
            ) and not node.name.startswith("test_"):
                body = node.body
                if len(body) > 1 and isinstance(body[0], ast.Expr):
                    body = body[1:]  # the docstring does not make a copy different
                shape = "".join(ast.dump(part) for part in [node.args, *node.decorator_list, *body])
                where = f"{name_of(path)}: {node.name}"
                if shape in seen:
                    problems.append(f"{where} is {seen[shape]}")
                seen.setdefault(shape, where)

    assert problems == [], "a helper of several modules belongs in tests/support"


def test_only_the_conftest_lives_at_the_top_and_test_folders_are_packages() -> None:
    assert sorted(path.name for path in TESTS.glob("*.py")) == ["conftest.py"]
    folders = {path.parent for path in python_files(TESTS) if path.parent != TESTS}
    assert [name_of(f) for f in sorted(folders) if not (f / "__init__.py").exists()] == []


def test_every_unit_test_module_mirrors_a_module_of_the_package() -> None:
    orphans = [
        name_of(path)
        for path in python_files(UNIT)
        if path.name.startswith("test_")
        and not (
            PACKAGE_SOURCE / path.parent.relative_to(UNIT) / f"{path.name[len('test_') :]}"
        ).exists()
    ]

    assert orphans == [], (
        "tests/unit/<path>/test_<name>.py tests src/deweloperuch_mcp/<path>/<name>.py"
    )


def test_modules_without_unit_tests_are_listed() -> None:
    """Not a failure: the list says where unit tests are missing (a warning in the summary)."""
    untested = sorted(
        str(path.relative_to(PACKAGE_SOURCE))
        for path in PACKAGE_SOURCE.rglob("*.py")
        if path.name != "__init__.py"
        and not (UNIT / path.parent.relative_to(PACKAGE_SOURCE) / f"test_{path.name}").exists()
    )

    if untested:
        warnings.warn(
            f"{len(untested)} modules without unit tests: " + ", ".join(untested), stacklevel=1
        )


def test_every_provider_of_fixtures_is_a_plugin() -> None:
    conftest = tree(TESTS / "conftest.py")
    plugins = next(
        ast.literal_eval(node.value)
        for node in conftest.body
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "pytest_plugins" for t in node.targets)
    )
    with_fixtures = {
        ".".join(path.relative_to(TESTS).with_suffix("").parts)
        for path in python_files(SUPPORT)
        if defines_fixtures(tree(path))
    }

    assert with_fixtures <= set(plugins)


def defines_fixtures(module: ast.Module) -> bool:
    """A function decorated with ``pytest.fixture`` or ``fixture`` (``from pytest import
    fixture``), called or not."""
    for node in ast.walk(module):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        for decorator in node.decorator_list:
            target = decorator.func if isinstance(decorator, ast.Call) else decorator
            if (isinstance(target, ast.Attribute) and target.attr == "fixture") or (
                isinstance(target, ast.Name) and target.id == "fixture"
            ):
                return True
    return False


@pytest.mark.parametrize(
    ("source", "found"),
    [
        ("import pytest\n@pytest.fixture\ndef a(): ...", True),
        ("import pytest\n@pytest.fixture(scope='session')\ndef a(): ...", True),
        ("from pytest import fixture\n@fixture\ndef a(): ...", True),
        ("from pytest import fixture\n@fixture(autouse=True)\nasync def a(): ...", True),
        ("# pytest.fixture in a comment\ndef a(): ...", False),
    ],
)
def test_fixture_providers_are_found_by_their_decorators(source: str, found: bool) -> None:
    assert defines_fixtures(ast.parse(source)) is found
