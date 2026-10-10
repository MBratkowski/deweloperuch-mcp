"""Live: the installed ``deweloperuch-mcp`` over stdio, through the SDK's ``ClientSession``.

One server for the module, so a repeated request comes from its cache. Module fixtures
remember what the first calls found (the city slug, an offer, its investment): a test
asks for what it needs and never relies on the order of the others. Every call ends
the session on a STOP or a service error and fails on backend details in the result
(``live.McpLive``). Assertions are about structure, ranges and consistency, never
about today's numbers.

Behaviours marked [W] below follow from the code and the discovery docs; the first live
run confirms them.
"""

import json
import math
import re
import warnings
from collections.abc import Iterator
from typing import Any

import pytest

from e2e.live import (
    SERVICE_CHANGED,
    SNAPSHOT,
    Budget,
    Call,
    McpLive,
    assert_listing_clean,
    mcp_server,
)

pytestmark = pytest.mark.live

TOOLS = ["search_locations", "search_offers", "get_offer", "get_investment"]
UNKNOWN_CITY = "nieistniejace-miasto"
UNKNOWN_INVESTMENT = "nieistniejaca-inwestycja-e2e"
MAX_PAGES = 20
SIZE_BUDGET = 8_000
SIZE_BUDGET_50 = 25_000
PRICE_RANGE = {"price_min": 400_000, "price_max": 700_000}
AREA_RANGE = {"area_min": 40, "area_max": 60}
SMALL_CITY = "sopot"
"""A city with few offers: 6 active ones in city-sales (T12, [P 2026-10-10])."""
STREET_QUERY = "mokot"
"""Finds the district Mokotów and the street Mokotów in Warszawa ([P 2026-10-09], sample
api.location_search, the same query and limit as search_locations sends)."""
SLUG = re.compile(r"[a-z0-9][a-z0-9-]*")
EVENT_KINDS = {"offer", "archived", "restored"}
OFFER_ITEM = {"offer_id", "investment_slug", "name", "status", "investment_name", "developer_name"}


# --- the server and what the first calls found ------------------------------------------


@pytest.fixture(scope="module")
def mcp(budget: Budget, tmp_path_factory: pytest.TempPathFactory) -> Iterator[McpLive]:
    log = tmp_path_factory.mktemp("mcp") / "server-stderr.log"
    with mcp_server(log, budget) as server:
        yield server


@pytest.fixture(scope="module")
def krakow(mcp: McpLive) -> dict[str, Any]:
    return locations(mcp, "Kraków")


@pytest.fixture(scope="module")
def city_slug(krakow: dict[str, Any]) -> str:
    cities = [i for i in krakow["items"] if i["kind"] == "city" and i["name"] == "Kraków"]
    assert cities, f"brak miasta Kraków w {krakow['items']}"
    slug: str = cities[0]["city_slug"]
    return slug


@pytest.fixture(scope="module")
def mokot(mcp: McpLive) -> dict[str, Any]:
    return locations(mcp, STREET_QUERY)


@pytest.fixture(scope="module")
def first_page(mcp: McpLive, city_slug: str) -> Call:
    return mcp.call_network("search_offers", city=city_slug)


@pytest.fixture(scope="module")
def fifty(mcp: McpLive, city_slug: str) -> Call:
    return mcp.call_network("search_offers", city=city_slug, per_page=50)


@pytest.fixture(scope="module")
def price_range(mcp: McpLive, city_slug: str) -> Call:
    return mcp.call_network("search_offers", city=city_slug, **PRICE_RANGE)


@pytest.fixture(scope="module")
def area_range(mcp: McpLive, city_slug: str) -> Call:
    return mcp.call_network("search_offers", city=city_slug, **AREA_RANGE)


@pytest.fixture(scope="module")
def polska_page(mcp: McpLive) -> Call:
    return mcp.call_network("search_offers", city="polska")


@pytest.fixture(scope="module")
def offer(first_page: Call) -> dict[str, Any]:
    items = first_page.data["items"]
    assert items, "pierwsza strona ofert jest pusta"
    found: dict[str, Any] = items[0]
    return found


@pytest.fixture(scope="module")
def investment(mcp: McpLive, offer: dict[str, Any]) -> Call:
    return mcp.call_network("get_investment", investment_slug=offer["investment_slug"])


# --- checks ----------------------------------------------------------------------------


def locations(mcp: McpLive, query: str) -> dict[str, Any]:
    result = mcp.call_network("search_locations", query=query).data
    # D4: total first and always there; null exactly when the list may be incomplete.
    assert list(result)[:3] == ["total", "returned", "truncated"]
    assert result["returned"] == len(result["items"])
    assert (result["total"] is None) == result["truncated"]
    if result["total"] is not None:
        assert result["total"] == result["returned"]
    for item in result["items"]:
        assert item["kind"] in {"city", "district", "street"}
        assert item["name"] and item["city"]
        assert SLUG.fullmatch(item["city_slug"]), item
    return result


def check_page(result: dict[str, Any], *, per_page: int, page: int = 1) -> list[dict[str, Any]]:
    """D4 counters consistent with each other and with the items."""
    total, items = result["total"], result["items"]
    assert (result["page"], result["per_page"]) == (page, per_page)
    assert result["returned"] == len(items)
    assert result["returned"] == max(0, min(per_page, total - (page - 1) * per_page))
    assert result["pages_available"] == min(MAX_PAGES, math.ceil(total / per_page))
    assert result["truncated"] == (total > MAX_PAGES * per_page)
    if result["truncated"]:
        assert "Zawęź filtry" in result["hint"]
    ids = [item["offer_id"] for item in items]
    assert len(set(ids)) == len(ids)
    for item in items:
        assert set(item) >= OFFER_ITEM, item
        assert item["offer_id"] > 0 and SLUG.fullmatch(item["investment_slug"]), item
        assert item.get("price", 1) > 0 and item.get("area_m2", 1) > 0, item
    found: list[dict[str, Any]] = items
    return found


def prices(items: list[dict[str, Any]]) -> list[float]:
    values = [item["price"] for item in items if "price" in item]
    assert values, "żadna oferta nie ma ceny"
    return values


def from_cache(call: Call, *, sent: int = 0) -> None:
    """The server's cache answered what ``call`` repeats: it sent only ``sent`` requests.

    Every endpoint the tools use sends ``max-age=28800`` without ``s-maxage``
    [P 2026-10-10], so the server keeps a reply ``DEFAULT_TTL`` (300 s) unless
    Cloudflare's ``Age`` is within 300 s of 28800 (``transport._ttl``); this module takes
    about a minute. No tolerance, then: only an endpoint with ``s-maxage=300`` (city-sales,
    which no tool uses) could expire during a run.
    """
    assert call.sent == sent, (
        f"{call.tool} {call.arguments}: {call.sent} zapytań zamiast {sent}; odpowiedź nie "
        "przyszła z cache serwera. Sprawdź Age i Cache-Control tej odpowiedzi (log serwera "
        "na DEBUG: 'TTL cache'): przy Age ≥ max-age TTL 0 jest zgodny z regułą D2"
    )


def check_investment(result: dict[str, Any]) -> None:
    returned, omitted = result["offers_returned"], result["offers_omitted"]
    assert returned == len(result["offers"]) and omitted >= 0
    assert result["truncated"] == (omitted > 0)
    statuses = [o["status"] for o in result["offers"]]
    assert statuses == sorted(statuses, key=lambda status: status != "active")  # active first
    total, active = result.get("offers_total"), result.get("offers_active")
    if total is not None and active is not None:
        assert active <= total
    if total is not None and total != returned + omitted:
        warnings.warn(
            f"{result['investment_slug']}: offers_total {total} ≠ zwrócone {returned} + "
            f"pominięte {omitted} (offers_total to liczba z serwisu)",
            stacklevel=2,
        )


# --- tools/list ------------------------------------------------------------------------


def test_tools_list_matches_the_snapshot(mcp: McpLive) -> None:
    tools, sent = mcp.list_tools()

    snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    shown = [tool.model_dump(mode="json", by_alias=True, exclude_none=True) for tool in tools]
    keys = ("name", "title", "description", "inputSchema", "outputSchema", "annotations")
    assert [{k: t.get(k) for k in keys} for t in shown] == [
        {k: t.get(k) for k in keys} for t in snapshot["tools"]
    ]
    assert [t["name"] for t in shown] == TOOLS
    assert all(t["annotations"] == {"readOnlyHint": True, "openWorldHint": True} for t in shown)
    assert mcp.init.server_info.name == snapshot["server"]["name"]
    assert mcp.init.instructions == snapshot["server"]["instructions"]
    assert sent == 0


def test_tools_list_has_no_backend_details(mcp: McpLive) -> None:
    """Descriptions, input and output schemas, field names included (D3)."""
    tools, sent = mcp.list_tools()

    assert_listing_clean([tool.model_dump(mode="json", by_alias=True) for tool in tools])
    assert sent == 0


# --- search_locations ------------------------------------------------------------------


def test_locations_a_city_gives_its_slug(city_slug: str) -> None:
    assert city_slug == "krakow"


def test_locations_a_district_gives_the_slug_of_its_city(mokot: dict[str, Any]) -> None:
    items = mokot["items"]

    districts = [i for i in items if i["kind"] == "district" and "Mokotów" in i["name"]]
    assert districts, items
    assert any(i["city_slug"] == "warszawa" for i in districts)


def test_locations_a_street_gives_the_slug_of_its_city(mokot: dict[str, Any]) -> None:
    """The same search (no request of its own): the street Mokotów in Warszawa."""
    items = mokot["items"]

    streets = [i for i in items if i["kind"] == "street" and "Mokotów" in i["name"]]
    assert streets, items
    assert any(i["city_slug"] == "warszawa" and i.get("street") == "Mokotów" for i in streets)


@pytest.mark.parametrize("name", ["Łódź", "Gdańsk"])
def test_locations_with_polish_letters(mcp: McpLive, name: str) -> None:
    result = locations(mcp, name)

    cities = [i for i in result["items"] if i["kind"] == "city" and i["name"] == name]
    assert cities, result["items"]
    assert cities[0]["city_slug"].isascii()


def test_locations_without_results(mcp: McpLive) -> None:
    result = locations(mcp, "zzqxv")

    assert (result["total"], result["returned"], result["items"]) == (0, 0, [])
    assert "zzqxv" in result["hint"]


def test_locations_a_too_short_query_is_refused_without_a_request(mcp: McpLive) -> None:
    call = mcp.call("search_locations", query="a")

    assert call.error and "query" in call.text
    assert call.sent == 0


# --- search_offers ---------------------------------------------------------------------


def test_offers_of_a_city_with_the_defaults(first_page: Call) -> None:
    result = first_page.data
    items = check_page(result, per_page=10)

    assert result["returned"] == 10
    assert all("city" not in item and "city_slug" not in item for item in items)
    assert first_page.sent == 1


def test_offers_50_per_page(fifty: Call) -> None:
    result = fifty.data

    check_page(result, per_page=50)
    assert result["returned"] == 50
    assert fifty.sent == 1


def test_offers_50_per_page_fit_their_size_budget(fifty: Call) -> None:
    assert len(fifty.text) < SIZE_BUDGET_50


def test_offers_page_2_has_other_offers(mcp: McpLive, city_slug: str, first_page: Call) -> None:
    result = mcp.call_network("search_offers", city=city_slug, page=2).data

    second = check_page(result, per_page=10, page=2)
    first = {item["offer_id"] for item in first_page.data["items"]}
    assert second and not first & {item["offer_id"] for item in second}


def test_offers_in_a_price_range(price_range: Call) -> None:
    items = check_page(price_range.data, per_page=10)

    assert all(400_000 <= price <= 700_000 for price in prices(items)), prices(items)


def test_offers_in_an_area_range(area_range: Call) -> None:
    items = check_page(area_range.data, per_page=10)

    areas = [item["area_m2"] for item in items if "area_m2" in item]
    assert areas and all(40 <= area <= 60 for area in areas), areas


@pytest.mark.parametrize(("sort", "descending"), [("price_asc", False), ("price_desc", True)])
def test_offers_sorted_by_price(mcp: McpLive, city_slug: str, sort: str, descending: bool) -> None:
    result = mcp.call_network("search_offers", city=city_slug, sort=sort).data

    values = prices(check_page(result, per_page=10))
    assert values == sorted(values, reverse=descending)


def test_offers_with_filters_and_sort_together(mcp: McpLive, city_slug: str) -> None:
    result = mcp.call_network(
        "search_offers",
        city=city_slug,
        price_min=300_000,
        price_max=900_000,
        area_min=30,
        area_max=70,
        sort="price_asc",
    ).data

    items = check_page(result, per_page=10)
    values = prices(items)
    assert values == sorted(values)
    assert all(300_000 <= price <= 900_000 for price in values)
    assert all(30 <= item["area_m2"] <= 70 for item in items if "area_m2" in item)


def test_offers_in_the_whole_country_name_their_city(polska_page: Call) -> None:
    items = check_page(polska_page.data, per_page=10)

    assert items and all(item["city"] and SLUG.fullmatch(item["city_slug"]) for item in items)


def test_offers_of_an_unknown_city_say_so(mcp: McpLive) -> None:
    """2026-10-10: the service answers 200 with Next.js's 404 marker, not a 404."""
    call = mcp.call_network("search_offers", city=UNKNOWN_CITY)

    assert call.error
    assert "nie zna miasta" in call.text and "search_locations" in call.text
    assert "polska" in call.text
    assert SERVICE_CHANGED not in call.text
    assert call.sent == 1


def test_offers_page_past_the_last_one(mcp: McpLive) -> None:
    """A known city with few offers, the page past its last one (T34).

    [W] Expected: an empty page with a hint naming the pages there are (the domain's
    hint for this case). If the service marks it as not found instead, the model reads
    "no such city": a known problem (xfail) for docs/open-questions.md.
    """
    small = mcp.call_network("search_offers", city=SMALL_CITY).data
    total, pages = small["total"], small["pages_available"]
    if total == 0 or pages >= MAX_PAGES:
        pytest.skip(f"{SMALL_CITY!r} nie ma małej liczby ofert (total {total})")
    check_page(small, per_page=10)
    page = pages + 1

    call = mcp.call_network("search_offers", city=SMALL_CITY, page=page)

    if call.error and "nie zna miasta" in call.text:
        pytest.xfail(
            f"Znany problem: strona {page} poza zakresem dla znanego miasta "
            f"{SMALL_CITY!r} daje „nie zna miasta” (digest 404 strony), a nie pustą stronę. "
            "Pozycja do docs/open-questions.md."
        )
    result = call.data
    assert result["page"] == page, (
        f"serwis zwrócił stronę {result['page']} zamiast {page} (przycięcie do ostatniej?): "
        "zachowanie inne niż zakładane [W]; ustal je w pages-rsc.md i w tym teście"
    )
    check_page(result, per_page=10, page=page)
    assert result["items"] == []
    assert f"Strona {page} jest pusta" in result["hint"]


def test_offers_price_min_above_price_max_is_refused_without_a_request(
    mcp: McpLive, city_slug: str
) -> None:
    call = mcp.call("search_offers", city=city_slug, price_min=700_000, price_max=500_000)

    assert call.error and "price_min" in call.text
    assert call.sent == 0


@pytest.mark.parametrize(
    ("arguments", "field"),
    [({"per_page": 100}, "per_page"), ({"page": 21}, "page"), ({"sort": "area_asc"}, "sort")],
)
def test_offers_arguments_off_the_schema_are_refused_without_a_request(
    mcp: McpLive, city_slug: str, arguments: dict[str, Any], field: str
) -> None:
    call = mcp.call("search_offers", city=city_slug, **arguments)

    assert call.error and field in call.text and "Input should" in call.text
    assert call.sent == 0  # the leak check of every call also refuses pydantic's docs links


def test_offers_numbers_as_text_are_the_same_request(
    mcp: McpLive, city_slug: str, first_page: Call
) -> None:
    """ "10" and "1" as text: the same page, so it comes from the server's cache."""
    call = mcp.call("search_offers", city=city_slug, per_page="10", page="1")

    from_cache(call)
    assert call.data["items"] == first_page.data["items"]


@pytest.mark.parametrize(
    ("arguments", "same_as"),
    [
        ({"price_min": "400000", "price_max": 700_000}, "price_range"),
        ({"area_min": "40", "area_max": "60"}, "area_range"),
    ],
)
def test_offers_filter_numbers_as_text_are_the_same_request(
    mcp: McpLive,
    city_slug: str,
    arguments: dict[str, Any],
    same_as: str,
    request: pytest.FixtureRequest,
) -> None:
    earlier: Call = request.getfixturevalue(same_as)

    call = mcp.call("search_offers", city=city_slug, **arguments)

    from_cache(call)
    assert call.data["items"] == earlier.data["items"]


@pytest.mark.parametrize("arguments", [{"price_min": None}, {"sort": ""}, {"sort": None}])
def test_offers_empty_or_null_optional_arguments_are_the_defaults(
    mcp: McpLive, city_slug: str, first_page: Call, arguments: dict[str, Any]
) -> None:
    """Models send null (or "") for what they leave out: the default request, cached."""
    call = mcp.call("search_offers", city=city_slug, **arguments)

    from_cache(call)
    assert call.data["items"] == first_page.data["items"]


def test_offers_result_of_10_fits_the_size_budget(first_page: Call) -> None:
    assert len(first_page.text) < SIZE_BUDGET


# --- search_offers: mistakes a model makes with `city` ---------------------------------


@pytest.mark.parametrize("city", ["Kraków", "Warszawa", "KRAKOW", ""])
def test_offers_city_that_is_not_a_slug_is_refused_without_a_request(
    mcp: McpLive, city: str
) -> None:
    """A name instead of a slug, capitals, nothing: refused by the services, which point
    to search_locations (the code: slugs are lowercase ASCII, nothing is guessed)."""
    call = mcp.call("search_offers", city=city)

    assert call.error
    assert call.text.startswith("city: ") and "search_locations" in call.text
    assert call.sent == 0


def test_offers_city_with_spaces_around_is_trimmed(
    mcp: McpLive, city_slug: str, first_page: Call
) -> None:
    call = mcp.call("search_offers", city=f" {city_slug} ")

    from_cache(call)
    assert call.data["items"] == first_page.data["items"]


def test_offers_district_slug_as_city_is_an_unknown_city(mcp: McpLive) -> None:
    """`mokotow` is a valid slug, so it is sent. [W] The service does not know it as a
    city: the model reads "no such city" with the way to the right slug."""
    call = mcp.call_network("search_offers", city="mokotow")

    assert call.error, f"serwis zna 'mokotow' jako miasto [W]: {call.text[:200]}"
    assert "nie zna miasta 'mokotow'" in call.text and "search_locations" in call.text
    assert call.sent == 1


# --- get_investment --------------------------------------------------------------------


def test_investment_with_the_default_limit(investment: Call, offer: dict[str, Any]) -> None:
    result = investment.data

    check_investment(result)
    assert result["investment_slug"] == offer["investment_slug"]
    assert result["offers_returned"] <= 20
    assert all("price_history" not in o for o in result["offers"])


def test_investment_limit_0_is_the_summary(
    mcp: McpLive, investment: Call, offer: dict[str, Any]
) -> None:
    full = investment.data
    call = mcp.call("get_investment", investment_slug=offer["investment_slug"], limit=0)

    result = call.data
    check_investment(result)
    assert (result["offers"], result["offers_returned"]) == ([], 0)
    from_cache(call)
    assert result["offers_omitted"] == full["offers_returned"] + full["offers_omitted"]


def test_investment_with_history(mcp: McpLive, investment: Call, offer: dict[str, Any]) -> None:
    call = mcp.call(
        "get_investment", investment_slug=offer["investment_slug"], include_history=True, limit=2
    )

    result = call.data
    check_investment(result)
    assert 1 <= result["offers_returned"] <= 2
    for item in result["offers"]:
        history = item["price_history"]
        assert history, item
        assert {event["kind"] for event in history} <= EVENT_KINDS
    from_cache(call, sent=1)  # the history; the investment comes from the cache


def test_investment_lists_the_offer_found_by_search(
    mcp: McpLive, investment: Call, offer: dict[str, Any]
) -> None:
    call = mcp.call("get_investment", investment_slug=offer["investment_slug"], limit=200)

    result = call.data
    ids = {o["offer_id"] for o in result["offers"]}
    if offer["offer_id"] not in ids and result["offers_omitted"]:
        pytest.skip("oferta z wyszukiwania jest poza limitem 200 ofert inwestycji")
    from_cache(call)
    assert offer["offer_id"] in ids


def test_investment_unknown(mcp: McpLive) -> None:
    call = mcp.call_network("get_investment", investment_slug=UNKNOWN_INVESTMENT)

    assert call.error and "Nie znaleziono inwestycji" in call.text
    assert call.sent == 1


# --- get_offer -------------------------------------------------------------------------


def test_offer_with_its_price_history(
    mcp: McpLive, investment: Call, offer: dict[str, Any]
) -> None:
    call = mcp.call(
        "get_offer", offer_id=offer["offer_id"], investment_slug=offer["investment_slug"]
    )

    result = call.data
    assert (result["offer_id"], result["investment_slug"]) == (
        offer["offer_id"],
        offer["investment_slug"],
    )
    assert result["price_history"]
    assert {event["kind"] for event in result["price_history"]} <= EVENT_KINDS
    if result.get("price") != offer.get("price"):
        warnings.warn(
            f"oferta {offer['offer_id']}: cena {result.get('price')} ≠ {offer.get('price')} "
            "z wyszukiwania (dane mogły się zmienić między wywołaniami)",
            stacklevel=1,
        )
    from_cache(call, sent=1)  # the history; the investment comes from the cache


def test_offer_outside_its_investment(
    mcp: McpLive, investment: Call, offer: dict[str, Any]
) -> None:
    call = mcp.call("get_offer", offer_id=999_999_999, investment_slug=offer["investment_slug"])

    assert call.error and "nie ma oferty" in call.text
    from_cache(call)


def test_offer_of_an_unknown_investment(mcp: McpLive, offer: dict[str, Any]) -> None:
    call = mcp.call_network(
        "get_offer", offer_id=offer["offer_id"], investment_slug=UNKNOWN_INVESTMENT
    )

    assert call.error and "Nie znaleziono inwestycji" in call.text
    assert call.sent == 1


def test_offer_from_another_city_found_in_the_whole_country(
    mcp: McpLive, polska_page: Call, city_slug: str
) -> None:
    """The chain a model follows from city=polska: an investment of another city than
    the first search, then one of its offers."""
    others = [i for i in polska_page.data["items"] if i["city_slug"] != city_slug]
    if not others:
        pytest.skip(f"wszystkie oferty z city=polska są z {city_slug!r}")
    found = others[0]

    investment = mcp.call_network("get_investment", investment_slug=found["investment_slug"])
    detail = mcp.call(
        "get_offer", offer_id=found["offer_id"], investment_slug=found["investment_slug"]
    )

    result = investment.data
    check_investment(result)
    assert (result["investment_slug"], result["city_slug"]) == (
        found["investment_slug"],
        found["city_slug"],
    )
    offer = detail.data
    assert (offer["offer_id"], offer["city_slug"]) == (found["offer_id"], found["city_slug"])
    assert offer["price_history"]
    from_cache(detail, sent=1)  # the history; the investment comes from the cache


# --- two calls at once -----------------------------------------------------------------


def test_two_calls_at_once_go_one_by_one_through_the_limiter(mcp: McpLive, city_slug: str) -> None:
    """Both succeed; their requests are logged about a second apart (shared limiter)."""
    calls, logged = mcp.parallel(
        ("search_offers", {"city": city_slug, "page": 3}),
        ("search_offers", {"city": "polska", "page": 2}),
    )

    for call in calls:
        check_page(call.data, per_page=10, page=call.arguments["page"])
    assert len(logged) == 2
    assert logged[1] - logged[0] >= 0.9, logged
