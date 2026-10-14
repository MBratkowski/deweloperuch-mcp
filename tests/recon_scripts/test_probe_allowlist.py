"""The read allowlist (``deweloperuch_mcp.allowlist``, re-exported by recon/allowlist.py)
matches the read channels documented in docs/discovery/."""

import ast
import itertools
import re

import pytest

import allowlist as recon_allowlist
from allowlist import (
    API_PATHS,
    DUMP_PATHS,
    EXCLUDED_API_PATHS,
    PAGE_ROUTES,
    match_api,
    match_dump,
    match_excluded_api,
    match_page,
)
from deweloperuch_mcp import allowlist as package_allowlist
from support.paths import REPO

ENDPOINTS = REPO / "docs" / "discovery" / "endpoints.md"
PAGES = REPO / "docs" / "discovery" / "pages-rsc.md"

PLACEHOLDER = re.compile(r"\{[^{}]*\}")


def documented_api_paths() -> list[str]:
    """Path templates of every ``### `GET /api/...``` heading, query and options cut off."""
    paths = []
    for line in ENDPOINTS.read_text(encoding="utf-8").splitlines():
        if line.startswith("### "):
            for request in re.findall(r"`GET (/api/[^`]*)`", line):
                paths.append(re.split(r"[?\[]", request, maxsplit=1)[0])
    return paths


def documented_page_routes() -> list[str]:
    """Routes in the ``### `/...``` headings of pages-rsc.md, siblings spelled out.

    - ``### `/a/{x}/b` i `/c` `` also documents ``/a/{x}/c`` (a trailing sibling
      replaces as many trailing segments as it has);
    - ``### `…/{inv}/raport` `` continues the latest route that ends with ``{inv}``.
    """
    routes: list[str] = []
    for line in PAGES.read_text(encoding="utf-8").splitlines():
        if not line.startswith("### "):
            continue
        tokens = [t for t in re.findall(r"`([^`]+)`", line) if t.startswith(("/", "…/"))]
        if not tokens:
            continue
        first, siblings = tokens[0], tokens[1:]
        if first.startswith("…/"):
            anchor, _, rest = first.removeprefix("…/").partition("/")
            base = next(r for r in reversed(routes) if r.rsplit("/", 1)[-1] == anchor)
            first = f"{base}/{rest}"
        routes.append(first)
        for sibling in siblings:
            depth = sibling.count("/")
            routes.append(first.rsplit("/", depth)[0] + sibling)
    return routes


def concrete(template: str) -> list[str]:
    """Example paths for a template: ``{a|b}`` gives each literal, other placeholders a slug."""
    choices = [
        m.group(0)[1:-1].split("|") if "|" in m.group(0) else ["przyklad-1"]
        for m in PLACEHOLDER.finditer(template)
    ]
    literals = PLACEHOLDER.split(template)
    return [
        "".join(itertools.chain.from_iterable(itertools.zip_longest(literals, combo, fillvalue="")))
        for combo in itertools.product(*choices)
    ]


# --- sync with the docs -------------------------------------------------------


def test_docs_parsers_find_the_documented_entries() -> None:
    """A changed heading format must not leave the sync tests below with nothing to check.

    At A#2 the docs had 34 API headings and 19 page routes.
    """
    assert len(documented_api_paths()) >= 30
    assert len(documented_page_routes()) >= 15


def test_api_allowlist_equals_documented_endpoints() -> None:
    documented = documented_api_paths()

    assert len(set(documented)) == len(documented), "duplicate heading in endpoints.md"
    assert sorted(API_PATHS + EXCLUDED_API_PATHS) == sorted(documented)
    assert set(API_PATHS).isdisjoint(EXCLUDED_API_PATHS)
    assert len(set(API_PATHS)) == len(API_PATHS)


def test_valuation_pdf_is_excluded() -> None:
    assert "/api/valuation-pdf" in EXCLUDED_API_PATHS
    assert match_api("/api/valuation-pdf") is None
    assert match_excluded_api("/api/valuation-pdf") == "/api/valuation-pdf"


@pytest.mark.parametrize("template", API_PATHS)
def test_every_api_template_matches_its_own_example(template: str) -> None:
    for path in concrete(template):
        assert match_api(path) == template


@pytest.mark.parametrize("route", documented_page_routes())
def test_every_documented_page_route_is_allowed(route: str) -> None:
    for path in concrete(route):
        assert match_page(path) is not None, path


def test_page_routes_are_all_documented() -> None:
    """No pattern beyond the docs: each one covers some documented route."""
    examples = [path for route in documented_page_routes() for path in concrete(route)]

    for template in PAGE_ROUTES:
        assert any(match_page(path) == template for path in examples), template


# --- what stays out -----------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        "/api/unknown",
        "/api/cities/",
        "/api/cities/extra",
        "/api/map/city-powiats",
        "/api/map/city-powiats/a/b",
        "/api/investments/1/sale-events/2",
        "/api/valuation-pdf",
        "/api",
        "/ceny-ofertowe/warszawa/mieszkania",
    ],
)
def test_api_rejects_undocumented_paths(path: str) -> None:
    assert match_api(path) is None


@pytest.mark.parametrize(
    "path",
    [
        "/",
        "/wycena",
        "/zglos-dewelopera",
        "/kalkulator-oszczedzania",
        "/statystyki",
        "/ceny-ofertowe/warszawa/mieszkania/extra",
        "/ceny-ofertowe/warszawa/deweloperzy/atal/nowy-targowek-vi/raport-mieszkania-",
        "/ceny-transakcyjne/warszawa/mieszkania/slug",
        "/ceny-transakcyjne/krakow/miasta",
        "/statystyki/ceny-transakcyjne/dzialki/warszawa",
        "/api/cities",
    ],
)
def test_page_rejects_undocumented_routes(path: str) -> None:
    assert match_page(path) is None


# --- one implementation, dumps ------------------------------------------------


@pytest.mark.parametrize("name", recon_allowlist.__all__)
def test_recon_allowlist_reexports_the_package_one(name: str) -> None:
    """probe and the package's transport check paths against one list."""
    assert getattr(recon_allowlist, name) is getattr(package_allowlist, name)


def test_recon_allowlist_defines_nothing_of_its_own() -> None:
    tree = ast.parse((REPO / "recon" / "allowlist.py").read_text(encoding="utf-8"))
    own = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef | ast.Assign)
        and not (isinstance(node, ast.Assign) and ast.unparse(node.targets[0]) == "__all__")
    ]

    assert own == []


def test_powiat_sales_is_a_documented_read_but_a_dump() -> None:
    """recon may read it (within its body limit); the package's client never does (D5)."""
    assert match_api("/api/map/powiat-sales/208") == "/api/map/powiat-sales/{powiatId}"
    assert match_dump("/api/map/powiat-sales/208") == "/api/map/powiat-sales/{powiatId}"


def test_dumps_are_documented_read_channels() -> None:
    assert set(DUMP_PATHS) <= set(API_PATHS) | set(PAGE_ROUTES)


@pytest.mark.parametrize(
    "path",
    [
        "/statystyki/ceny-transakcyjne/mieszkania/warszawa",
        "/statystyki/ceny-transakcyjne/domy/sopot",
    ],
)
def test_stats_page_with_raw_transactions_is_a_documented_read_but_a_dump(path: str) -> None:
    """D5 rawTransactions: recon may read the page; the package's client never does."""
    assert match_page(path) == "/statystyki/ceny-transakcyjne/{mieszkania|domy}/{city}"
    assert match_dump(path) == "/statystyki/ceny-transakcyjne/{mieszkania|domy}/{city}"


@pytest.mark.parametrize(
    "path",
    [
        "/api/map/powiat-stats",
        "/api/map/powiat-investments/208",
        "/api/cities",
        "/statystyki/ceny-transakcyjne/mieszkania/warszawa/mapa",
        "/ceny-transakcyjne/warszawa/mieszkania",
    ],
)
def test_other_endpoints_are_not_dumps(path: str) -> None:
    assert match_dump(path) is None
