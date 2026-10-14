"""The golden cases of ``deweloperuch developers get`` (tests/golden/cli/<case>.json)."""

from support.golden.cli import DEVELOPERS, RSC, Case, case
from support.providers.routes.developer_profiles import developer_routes
from support.providers.rsc import (
    DEVELOPER_UNKNOWN,
    UNKNOWN_DEVELOPER,
    raw,
)

CASES: dict[str, Case] = {
    # developers get
    "help_developers_get": case(*DEVELOPERS, "--help"),
    "developers_get": case(*DEVELOPERS, "atal", "--city", "warszawa", service=developer_routes),
    "developers_get_json": case(
        *DEVELOPERS, "atal", "--city", "warszawa", "--json", service=developer_routes
    ),
    "developers_get_whole_country": case(*DEVELOPERS, "atal", service=developer_routes),
    "developers_get_limit_3": case(*DEVELOPERS, "atal", "--limit", "3", service=developer_routes),
    "developers_get_unknown": case(
        *DEVELOPERS, UNKNOWN_DEVELOPER, "--city", "warszawa", service=developer_routes
    ),
    "developers_get_page_without_data": case(
        *DEVELOPERS,
        "atal",
        "--city",
        "warszawa",
        service=lambda r: r.get(path="/ceny-ofertowe/warszawa/deweloperzy/atal").respond(
            200,
            content=raw(DEVELOPER_UNKNOWN).replace(b"Deweloper nie znaleziony", b"Inny tekst xx"),
            headers=RSC,
        ),
    ),
    "developers_get_slug_capitals": case(*DEVELOPERS, "ATAL", service=developer_routes),
    "developers_get_limit_0": case(*DEVELOPERS, "atal", "--limit", "0", service=developer_routes),
}
