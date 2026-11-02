"""The golden cases of ``deweloperuch developers get`` (tests/golden/cli/<case>.json)."""

from deweloperuch_mcp.flight import NOT_FOUND_DIGEST
from support.golden.cli import DEVELOPERS, RSC, Case, case
from support.golden.routes import lookup_failed
from support.providers.routes.developer_profiles import developer_routes
from support.providers.rsc import (
    DEVELOPER_UNKNOWN_20261031,
    UNKNOWN_DEVELOPER,
    raw,
)

WITHOUT_DATA_NOR_MARKER = raw(DEVELOPER_UNKNOWN_20261031).replace(
    NOT_FOUND_DIGEST.encode(), b"NEXT_HTTP_ERROR_FALLBACK;500"
)
"""The 2.0 page of an unknown developer without Next.js's 404 marker: a changed page."""

CASES: dict[str, Case] = {
    # developers get
    "help_developers_get": case(*DEVELOPERS, "--help"),
    "developers_get": case(*DEVELOPERS, "atal", "--city", "warszawa", service=developer_routes),
    "developers_get_json": case(
        *DEVELOPERS, "atal", "--city", "warszawa", "--json", service=developer_routes
    ),
    "developers_get_whole_country": case(*DEVELOPERS, "atal", service=developer_routes),
    "developers_get_limit_3": case(*DEVELOPERS, "atal", "--limit", "3", service=developer_routes),
    "developers_get_thousands": case(
        *DEVELOPERS, "dom-development", "--city", "warszawa", service=developer_routes
    ),
    "developers_get_single_city": case(
        *DEVELOPERS, "ceres-development", "--city", "warszawa", service=developer_routes
    ),
    "developers_get_without_offers": case(
        *DEVELOPERS, "atal", "--city", "bialystok", service=developer_routes
    ),
    "developers_get_unknown": case(
        *DEVELOPERS,
        UNKNOWN_DEVELOPER,
        "--city",
        "warszawa",
        service=(developer_routes, lookup_failed("warszawa")),
    ),
    "developers_get_page_without_data": case(
        *DEVELOPERS,
        "atal",
        "--city",
        "warszawa",
        service=lambda r: r.get(path="/ceny-ofertowe/warszawa/deweloperzy/atal").respond(
            200, content=WITHOUT_DATA_NOR_MARKER, headers=RSC
        ),
    ),
    "developers_get_slug_capitals": case(*DEVELOPERS, "ATAL", service=developer_routes),
    "developers_get_limit_0": case(*DEVELOPERS, "atal", "--limit", "0", service=developer_routes),
}
