"""The golden cases of ``deweloperuch developers search`` (tests/golden/cli/<case>.json)."""

from support.golden.cli import INJECTED_BODY, Case, case
from support.golden.routes import developers_with
from support.providers.routes.developer_search import developer_search_route

CASES: dict[str, Case] = {
    "help_developers_search": case("developers", "search", "--help"),
    # developers search
    "developers_search": case("developers", "search", "atal", service=developer_search_route),
    "developers_search_json": case(
        "developers", "search", "atal", "--json", service=developer_search_route
    ),
    "developers_search_limit_20": case(
        "developers", "search", "Dom Development", "--limit", "20", service=developer_search_route
    ),
    "developers_search_truncated": case(
        "developers", "search", "dom", service=developers_with(5, total=12, more=True)
    ),
    "developers_search_truncated_json": case(
        "developers", "search", "dom", "--json", service=developers_with(5, total=12, more=True)
    ),
    "developers_search_more_without_total": case(
        "developers", "search", "dom", service=developers_with(5, total=5, more=True)
    ),
    "developers_search_nothing": case(
        "developers", "search", "xyzzy", service=developers_with(0, total=0, more=False)
    ),
    "developers_search_too_short": case(
        "developers", "search", "a", service=developer_search_route
    ),
    "developers_search_limit_0": case(
        "developers", "search", "atal", "--limit", "0", service=developer_search_route
    ),
    "developers_search_limit_21": case(
        "developers", "search", "atal", "--limit", "21", service=developer_search_route
    ),
    "developers_search_limit_text": case(
        "developers", "search", "atal", "--limit", "x", service=developer_search_route
    ),
    "developers_search_without_name": case("developers", "search", service=developer_search_route),
    "developers_search_500": case(
        "developers",
        "search",
        "atal",
        service=lambda r: r.get(path="/api/developers").respond(500, text=INJECTED_BODY),
    ),
    "developers_search_429": case(
        "developers",
        "search",
        "atal",
        service=lambda r: r.get(path="/api/developers").respond(
            429, headers={"Retry-After": "300"}
        ),
    ),
}
