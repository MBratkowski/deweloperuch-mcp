"""The golden cases of the MCP tool ``search_developers`` (tests/golden/mcp/<case>.json)."""

from support.golden.mcp import HTML, INJECTED, Case, case
from support.golden.routes import developers_with
from support.providers.routes.developer_search import developer_search_route

CASES: dict[str, Case] = {
    # search_developers
    "developers": case("search_developers", developer_search_route, name="atal"),
    "developers_limit_20": case("search_developers", developer_search_route, name="atal", limit=20),
    "developers_limit_text": case(
        "search_developers", developer_search_route, name="  Dom Development ", limit=" 3 "
    ),
    "developers_limit_null": case(
        "search_developers", developer_search_route, name="atal", limit=None
    ),
    "developers_truncated": case(
        "search_developers", developers_with(5, total=12, more=True), name="dom"
    ),
    "developers_truncated_at_20": case(
        "search_developers", developers_with(20, total=40, more=True), name="dom", limit=20
    ),
    "developers_more_without_total": case(
        "search_developers", developers_with(5, total=5, more=True), name="dom"
    ),
    "developers_more_than_the_limit": case(
        "search_developers", developers_with(7, total=7, more=False), name="dom", limit=3
    ),
    "developers_nothing": case(
        "search_developers", developers_with(0, total=0, more=False), name="xyzzy"
    ),
    "developers_name_too_short": case("search_developers", developer_search_route, name="a"),
    "developers_without_name": case("search_developers", developer_search_route),
    "developers_name_number": case("search_developers", developer_search_route, name=42),
    "developers_limit_0": case("search_developers", developer_search_route, name="atal", limit=0),
    "developers_limit_21": case("search_developers", developer_search_route, name="atal", limit=21),
    "developers_limit_true": case(
        "search_developers", developer_search_route, name="atal", limit=True
    ),
    "developers_twice_one_request": case(
        "search_developers",
        developer_search_route,
        then=(("search_developers", {"name": "atal"}),),
        name="atal",
    ),
    "developers_500": case(
        "search_developers",
        lambda r: r.get(path="/api/developers").respond(500, text=INJECTED),
        name="atal",
    ),
    "developers_403": case(
        "search_developers", lambda r: r.get(path="/api/developers").respond(403), name="atal"
    ),
    "developers_html": case(
        "search_developers",
        lambda r: r.get(path="/api/developers").respond(200, text=INJECTED, headers=HTML),
        name="atal",
    ),
}
