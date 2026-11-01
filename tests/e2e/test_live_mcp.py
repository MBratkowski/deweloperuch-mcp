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

import datetime as dt
import json
import math
import re
import urllib.parse
import warnings
from collections.abc import Iterator
from typing import Any

import pytest

from deweloperuch_mcp.identity import BASE_URL
from support.e2e.live import (
    SERVICE_CHANGED,
    Budget,
    Call,
    McpLive,
    assert_listing_clean,
    keys,
    mcp_server,
    page_url,
    run_probe,
)
from support.paths import SNAPSHOT

pytestmark = pytest.mark.live

TOOLS = [
    "search_locations",
    "search_offers",
    "get_offer",
    "search_investments",
    "get_investment",
    "search_developers",
    "get_developer",
    "get_market_statistics",
    "get_transaction_statistics",
    "rank_locations",
    "get_building",
    "estimate_property_value",
    "get_government_statistics",
]
UNKNOWN_CITY = "nieistniejace-miasto"
UNKNOWN_INVESTMENT = "nieistniejaca-inwestycja-e2e"
UNKNOWN_LOCATION = "nieistniejaca-lokalizacja-e2e"
MAX_PAGES = 20
SIZE_BUDGET = 8_000
SIZE_BUDGET_50 = 27_500
"""A page of 50 offers: about 25k with the developer's slug (2026-10-13)."""
SIZE_BUDGET_DEVELOPER = 15_000
"""get_developer with the default limit: about 8.5k for 20 investments [P 2026-10-31]."""
UNKNOWN_DEVELOPER = "nieistniejacy-deweloper-e2e"
PRICE_RANGE = {"price_min": 400_000, "price_max": 700_000}
AREA_RANGE = {"area_min": 40, "area_max": 60}
SMALL_CITY = "sopot"
"""A city with few offers: 6 active ones in city-sales (T12, [P 2026-10-10]), 8 in the offer
snapshot [P 2026-10-31]."""
DISTRICT_SLUGS = {"Mokotów": "mokotow", "Praga-Południe": "praga-poludnie"}
"""The slugs the service gives these districts of Warszawa (the links of its offers list,
[P 2026-10-31]): the path of a district's list in a result."""
UNKNOWN_DISTRICT = "Nieistniejąca Dzielnica E2E"
STREET_QUERY = "mokot"
"""Finds the district Mokotów and the street Mokotów in Warszawa ([P 2026-10-09], sample
api.location_search, the same query and limit as search_locations sends)."""
SLUG = re.compile(r"[a-z0-9][a-z0-9-]*")
PAGES = BASE_URL + "/ceny-ofertowe"
"""Public pages of the service: the only addresses a result may hold (D12, 2026-10-11)."""
EVENT_KINDS = {"offer", "archived", "restored"}
STATS = BASE_URL + "/statystyki"
"""The statistics pages (D12): a government stats_url is ``{STATS}/{location}/dane-rzadowe``
at a section (moved there on 2026-10-29)."""
PERIOD = {
    "year": re.compile(r"\d{4}"),
    "quarter": re.compile(r"\d{4}-Q[1-4]"),
    "month": re.compile(r"\d{4}-(?:0[1-9]|1[0-2])"),
}
NBP_SERIES = ["primary_asking", "primary_transaction", "secondary_asking", "secondary_transaction"]
CITY_SECTIONS = {
    "average_area": "gus-srednia-powierzchnia",
    "wages": "gus-wynagrodzenia",
    "dwellings_quarterly": "gus-mieszkania",
    "population": "gus-wiek",
}
"""The section of some datasets on the page of a city: the ids of ``warszawa`` [P 2026-10-31,
tests/fixtures/rsc/stats_gov_warszawa_20261031.rsc]; other cities [W]. A chart, a chart
with notes and rows: the small city is read on the first three."""
OFFER_ITEM = {
    "offer_id",
    "investment_slug",
    "name",
    "status",
    "investment_name",
    "developer_name",
    "developer_slug",
}
SORTS = {
    "price_asc": ("amount", "asc"),
    "price_desc": ("amount", "desc"),
    "price_per_m2_asc": ("price_per_sqm", "asc"),
    "price_per_m2_desc": ("price_per_sqm", "desc"),
    "area_asc": ("size", "asc"),
    "area_desc": ("size", "desc"),
    "biggest_drop": ("start_amount_difference_percent", "asc"),
}
"""The ``sortBy`` and ``sortOrder`` search_offers sends for each order."""


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
def polska_area(mcp: McpLive) -> Call:
    return mcp.call_network("get_government_statistics", location="polska", dataset="average_area")


@pytest.fixture(scope="module")
def warszawa_nbp(mcp: McpLive) -> Call:
    return mcp.call_network("get_government_statistics", location="warszawa", dataset="nbp_prices")


@pytest.fixture(scope="module")
def aggregate_area(mcp: McpLive) -> Call:
    return mcp.call_network("get_government_statistics", location="7-miast", dataset="average_area")


@pytest.fixture(scope="module")
def small_city_area(mcp: McpLive) -> Call:
    return mcp.call_network(
        "get_government_statistics", location=SMALL_CITY, dataset="average_area"
    )


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


def list_query(
    *,
    price_min: object = None,
    price_max: object = None,
    area_min: object = None,
    area_max: object = None,
    price_per_m2_min: object = None,
    price_per_m2_max: object = None,
    district: object = None,
    price_dropped: object = False,
    status: object = None,
    sort: object = None,
    page: object = 1,
    per_page: object = 10,
) -> list[tuple[str, str]]:
    """The query search_offers sends for these tool arguments, in its order: open ranges
    end at the UI's sentinels (99999999 PLN, 9999 m², 999999 PLN/m²), null and "" mean
    "not given". A district is the list's path, not a parameter (since 2026-10-31)."""

    def given(value: object) -> bool:
        return value is not None and value != ""

    query: list[tuple[str, str]] = []
    for name, low, high, top in (
        ("filterPrice", price_min, price_max, 99_999_999),
        ("filterSize", area_min, area_max, 9_999),
        ("filterPricePerM2", price_per_m2_min, price_per_m2_max, 999_999),
    ):
        if given(low) or given(high):
            low_value = int(str(low)) if given(low) else 0
            high_value = int(str(high)) if given(high) else top
            query.append((name, f"{low_value}-{high_value}"))
    if price_dropped:
        query.append(("filterPriceChange", "decrease"))
    if status == "archived":
        query.append(("filterStatus", "archived"))
    elif status == "all":
        query.append(("includeArchived", "true"))
    if given(sort):
        sort_by, sort_order = SORTS[str(sort)]
        query += [("sortBy", sort_by), ("sortOrder", sort_order)]
    # [P 2026-10-29] the first page goes without `page`: the service redirects `page=1`.
    if int(str(page)) > 1:
        query.append(("page", str(int(str(page)))))
    query.append(("perPage", str(int(str(per_page)))))
    return query


def check_page(result: dict[str, Any], city: str, **arguments: Any) -> list[dict[str, Any]]:
    """D4 counters consistent with each other and with the items; the links (D12) of the
    list (the city's list or its district's, the arguments as the query, no _rsc) and of
    each item's investment."""
    district = arguments.get("district")
    where = [city] if district is None else [city, DISTRICT_SLUGS[district]]
    per_page = int(str(arguments.get("per_page") or 10))
    page = int(str(arguments.get("page") or 1))
    total, items = result["total"], result["items"]
    assert (result["page"], result["per_page"]) == (page, per_page)
    assert result["returned"] == len(items)
    assert result["returned"] == max(0, min(per_page, total - (page - 1) * per_page))
    assert result["pages_available"] == min(MAX_PAGES, math.ceil(total / per_page))
    assert result["truncated"] == (total > MAX_PAGES * per_page)
    if result["truncated"]:
        assert "Zawęź filtry" in result["hint"]
    url = urllib.parse.urlsplit(result["list_url"])
    assert result["list_url"].startswith(page_url(*where, "mieszkania") + "?"), result["list_url"]
    assert urllib.parse.parse_qsl(url.query) == list_query(**arguments), result["list_url"]
    ids = [item["offer_id"] for item in items]
    assert len(set(ids)) == len(ids)
    for item in items:
        assert set(item) >= OFFER_ITEM, item
        assert item["offer_id"] > 0 and SLUG.fullmatch(item["investment_slug"]), item
        assert item.get("price", 1) > 0 and item.get("area_m2", 1) > 0, item
        assert "city" not in item and "city_slug" not in item, item  # a search of one city
        if district is not None:  # [P 2026-10-31] the district's list: its own offers
            assert item.get("district") == district, item
        # The city segment comes from the offer's own data, which the result does not
        # show: any slug passes.
        slug = re.escape(urllib.parse.quote(item["investment_slug"], safe=""))
        link = rf"{re.escape(PAGES)}/[^/?#]+/deweloperzy/[^/?#]+/{slug}"
        assert re.fullmatch(link, item["investment_url"]), item
    found: list[dict[str, Any]] = items
    return found


def prices(items: list[dict[str, Any]]) -> list[float]:
    values = [item["price"] for item in items if "price" in item]
    assert values, "żadna oferta nie ma ceny"
    return values


def from_cache(call: Call, *, sent: int = 0) -> None:
    """The server's cache answered what ``call`` repeats: it sent only ``sent`` requests.

    The pages and routes these calls repeat send a ``max-age`` without ``s-maxage``: the
    2.0 pages ``private, max-age=172800, must-revalidate`` [P 2026-10-31], the 1.0 ones
    ``max-age=28800`` [P 2026-10-10]. So the server keeps a reply ``DEFAULT_TTL`` (300 s)
    unless Cloudflare's ``Age`` is within 300 s below the ``max-age``; an ``Age`` at or
    above it (the GUS page ``polska`` on 1.0: ``age: 69574`` [P 2026-10-13]) gives
    ``DEFAULT_TTL`` too (D2, clarification of 2026-10-13; ``transport._ttl``). This module
    takes about two minutes. No tolerance, then. ``offer-snapshot``
    (``get_market_statistics``) has ``s-maxage=3600`` [P 2026-10-31]: its repeat is not checked
    with this (an ``Age`` just under 3600 leaves its TTL only seconds).
    """
    assert call.sent == sent, (
        f"{call.tool} {call.arguments}: {call.sent} zapytań zamiast {sent}; odpowiedź nie "
        "przyszła z cache serwera. Sprawdź Age i Cache-Control tej odpowiedzi (log serwera "
        "na DEBUG: 'TTL cache'): TTL 0 daje tylko no-store, no-cache albo max-age=0 (D2)"
    )


def check_page_links(result: dict[str, Any]) -> None:
    """D12: the investment's page and the developer's profile, from the result's slugs."""
    city, developer = result["city_slug"], result["developer"]["developer_slug"]
    investment = page_url(city, "deweloperzy", developer, result["investment_slug"])
    assert result["investment_url"] == investment
    assert result["developer_url"] == page_url(city, "deweloperzy", developer)


def check_investment(result: dict[str, Any]) -> None:
    check_page_links(result)
    assert all(not any(key.endswith("_url") for key in o) for o in result["offers"])
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


def test_offers_of_a_city_with_the_defaults(first_page: Call, city_slug: str) -> None:
    result = first_page.data
    items = check_page(result, city_slug)

    assert result["returned"] == 10 == len(items)
    assert first_page.sent == 1


def test_offers_50_per_page(fifty: Call, city_slug: str) -> None:
    """[W] ``perPage=50`` on 2.0 (10 and 100 are [P 2026-10-31], T29): a page of 50."""
    result = fifty.data

    check_page(result, city_slug, per_page=50)
    assert result["returned"] == 50
    assert fifty.sent == 1


def test_offers_50_per_page_fit_their_size_budget(fifty: Call) -> None:
    assert len(fifty.text) < SIZE_BUDGET_50


def test_offers_page_2_has_other_offers(mcp: McpLive, city_slug: str, first_page: Call) -> None:
    result = mcp.call_network("search_offers", city=city_slug, page=2).data

    second = check_page(result, city_slug, page=2)
    first = {item["offer_id"] for item in first_page.data["items"]}
    assert second and not first & {item["offer_id"] for item in second}


def test_offers_in_a_price_range(price_range: Call, city_slug: str) -> None:
    items = check_page(price_range.data, city_slug, **PRICE_RANGE)

    assert all(400_000 <= price <= 700_000 for price in prices(items)), prices(items)


def test_offers_in_an_area_range(area_range: Call, city_slug: str) -> None:
    items = check_page(area_range.data, city_slug, **AREA_RANGE)

    areas = [item["area_m2"] for item in items if "area_m2" in item]
    assert areas and all(40 <= area <= 60 for area in areas), areas


@pytest.mark.parametrize(("sort", "descending"), [("price_asc", False), ("price_desc", True)])
def test_offers_sorted_by_price(mcp: McpLive, city_slug: str, sort: str, descending: bool) -> None:
    result = mcp.call_network("search_offers", city=city_slug, sort=sort).data

    values = prices(check_page(result, city_slug, sort=sort))
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

    items = check_page(
        result,
        city_slug,
        price_min=300_000,
        price_max=900_000,
        area_min=30,
        area_max=70,
        sort="price_asc",
    )
    values = prices(items)
    assert values == sorted(values)
    assert all(300_000 <= price <= 900_000 for price in values)
    assert all(30 <= item["area_m2"] <= 70 for item in items if "area_m2" in item)


def test_offers_of_the_whole_country_are_refused_without_a_request(mcp: McpLive) -> None:
    """[P 2026-10-29] the service's list of Poland is a list of cities, not of offers: refused
    before any request, pointing to one city (search_locations)."""
    call = mcp.call("search_offers", city="polska")

    assert call.error and call.text.startswith("city=polska nie działa"), call.text
    assert "search_locations" in call.text
    assert call.sent == 0


def test_offers_of_an_unknown_city_say_so(mcp: McpLive) -> None:
    """[P 2026-10-31] the service answers 200 with Next.js's 404 marker, not a 404."""
    call = mcp.call_network("search_offers", city=UNKNOWN_CITY)

    assert call.error
    assert "nie zna miasta" in call.text and "search_locations" in call.text
    assert "polska" not in call.text
    assert SERVICE_CHANGED not in call.text
    assert call.sent == 1


def test_offers_page_past_the_last_one(mcp: McpLive) -> None:
    """A known city with few offers, the page past its last one (T34).

    [P 2026-10-31] The 2.0 list answers it with the 404 marker of an unknown city, so
    the tool names both readings and points to page=1. An empty page with the domain's
    hint, the answer expected before [W], would also pass.
    """
    small = mcp.call_network("search_offers", city=SMALL_CITY).data
    total, pages = small["total"], small["pages_available"]
    if total == 0 or pages >= MAX_PAGES:
        pytest.skip(f"{SMALL_CITY!r} nie ma małej liczby ofert (total {total})")
    check_page(small, SMALL_CITY)
    page = pages + 1

    call = mcp.call_network("search_offers", city=SMALL_CITY, page=page)

    if call.error:
        # [P 2026-10-31] the 2.0 list answers a page past its last one with the 404 marker
        # of an unknown city: the tool names both readings and points to page=1.
        assert f"nie ma strony {page} tej listy" in call.text and "page=1" in call.text, call.text
        return
    result = call.data
    assert result["page"] == page, (
        f"serwis zwrócił stronę {result['page']} zamiast {page} (przycięcie do ostatniej?): "
        "zachowanie inne niż zakładane [W]; ustal je w pages-rsc.md i w tym teście"
    )
    check_page(result, SMALL_CITY, page=page)
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
    [({"per_page": 100}, "per_page"), ({"page": 21}, "page"), ({"sort": "rooms_asc"}, "sort")],
)
def test_offers_arguments_off_the_schema_are_refused_without_a_request(
    mcp: McpLive, city_slug: str, arguments: dict[str, Any], field: str
) -> None:
    call = mcp.call("search_offers", city=city_slug, **arguments)

    assert call.error and call.text.startswith("Błędny argument narzędzia search_offers: ")
    assert f"{field} musi być " in call.text
    assert call.sent == 0  # the leak check of every call also refuses pydantic's docs links


def test_offers_numbers_as_text_are_the_same_request(
    mcp: McpLive, city_slug: str, first_page: Call
) -> None:
    """ "10" and "1" as text: the same page, so it comes from the server's cache."""
    call = mcp.call("search_offers", city=city_slug, per_page="10", page="1")

    from_cache(call)
    assert call.data["items"] == first_page.data["items"]
    assert call.data["list_url"] == first_page.data["list_url"]  # same request, same link


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
    assert call.data["list_url"] == earlier.data["list_url"]  # same request, same link


@pytest.mark.parametrize("arguments", [{"price_min": None}, {"sort": ""}, {"sort": None}])
def test_offers_empty_or_null_optional_arguments_are_the_defaults(
    mcp: McpLive, city_slug: str, first_page: Call, arguments: dict[str, Any]
) -> None:
    """Models send null (or "") for what they leave out: the default request, cached."""
    call = mcp.call("search_offers", city=city_slug, **arguments)

    from_cache(call)
    assert call.data["items"] == first_page.data["items"]
    assert call.data["list_url"] == first_page.data["list_url"]  # same request, same link


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
    assert call.data["list_url"] == first_page.data["list_url"]  # same request, same link


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
    """[P 2026-10-30] (docs/discovery/endpoints.md, ``map/investments/visible``, 127 of 127
    offers): a history is oldest first, starts at the price minus the change since the
    start and ends at the current price, with a price for an active offer and the
    withdrawal for an archived one. The client reads the event types by their position
    (D21): a deploy that moves them would break this, not the call. Since 2.0 the histories
    come in the investment's own answer, which the ``investment`` fixture got: the server's
    cache answers the whole call."""
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
        dates = [event.get("date", "") for event in history]
        assert dates == sorted(dates), item
        last = history[-1]
        assert last.get("price") == pytest.approx(item.get("price"), abs=1), item
        if item["status"] in ("active", "archived"):
            assert last["kind"] == ("offer" if item["status"] == "active" else "archived"), item
        change = item.get("price_change_since_start")
        if change is not None and "price" in item:
            assert history[0].get("price") == pytest.approx(item["price"] - change, abs=1), item
    from_cache(call)  # the histories come with the investment


def test_investment_history_agrees_with_the_offer_history(
    mcp: McpLive, investment: Call, offer: dict[str, Any]
) -> None:
    """[P 2026-10-30] offer 33103: the events of the investment's answer equal, event for
    event, those of ``get_offer``, whose source names their types. The investment's answer
    gives a type as a position in a table of the client's code (D21), so a reordered table
    would mislabel events without an error: the two are compared live, on the offer with
    the most kinds of events (a return first, then a withdrawal), as a swap of two types
    shows only where both occur. Every offer from the cached answer (``limit=200``, no
    request); another offer than the search's, so ``test_offer_with_its_price_history``
    still sends its own request. The answers may come from the CDN at different moments:
    the shorter history must be the start of the longer one, a different length is only a
    warning."""
    every = mcp.call(
        "get_investment", investment_slug=offer["investment_slug"], include_history=True, limit=200
    )
    others = [o for o in every.data["offers"] if o["offer_id"] != offer["offer_id"]]
    if not others:
        pytest.skip("inwestycja nie ma innej oferty niż ta z wyszukiwania")

    def kinds(item: dict[str, Any]) -> tuple[bool, bool]:
        found = {event["kind"] for event in item["price_history"]}
        return ("restored" in found, "archived" in found)

    item = max(others, key=kinds)  # the first of the best
    call = mcp.call(
        "get_offer", offer_id=item["offer_id"], investment_slug=offer["investment_slug"]
    )

    shown, named = item["price_history"], call.data["price_history"]
    common = min(len(shown), len(named))
    assert shown[:common] == named[:common], (item["offer_id"], shown, named)
    if len(shown) != len(named):
        warnings.warn(
            f"oferta {item['offer_id']}: {len(shown)} zdarzeń w get_investment, {len(named)} w "
            "get_offer (odpowiedzi serwisu z różnych chwil)",
            stacklevel=1,
        )
    from_cache(every)  # the histories come with the investment
    from_cache(call, sent=1)  # the offer's history; the investment comes from the cache


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


def test_the_investment_link_leads_to_its_page(budget: Budget, investment: Call) -> None:
    """The one link the suite follows (1 request, probe): the investment's page exists
    and holds that investment. The other links are checked for their pattern only.
    [P 2026-10-30, the saved 2.0 page of an investment] the page's ``breadcrumbs`` end with
    the investment's name."""
    result = investment.data
    path = result["investment_url"].removeprefix(BASE_URL)

    run = run_probe(budget, "page", path, "--prop", "breadcrumbs", "--full")

    assert run.code == 0, (run.code, run.stderr)
    crumbs = [item for item in json.loads(run.stdout) if isinstance(item, dict)]
    assert crumbs and crumbs[-1].get("label") == result["name"], crumbs


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
    check_page_links(result)
    assert result["investment_url"] == offer["investment_url"]  # as in the search
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


# --- get_government_statistics ---------------------------------------------------------


def check_statistics(result: dict[str, Any], location: str, dataset: str, section: str) -> None:
    """D4 counters, periods of the frequency in time order, values aligned with them, the
    link to the section of the page (D12)."""
    assert (result["location_slug"], result["dataset"]) == (location, dataset)
    total, returned = result["total"], result["returned"]
    assert returned == min(12, total) == len(result["periods"]) and returned > 0
    assert result["truncated"] == (total > returned)
    assert ("hint" in result) == result["truncated"]
    pattern = PERIOD[result["frequency"]]
    assert all(pattern.fullmatch(period) for period in result["periods"]), result["periods"]
    assert result["periods"] == sorted(set(result["periods"]))
    assert result["available_from"] <= result["periods"][0]
    assert result["series"]
    for series in result["series"]:
        assert len(series["values"]) == returned, series
    assert result["stats_url"] == f"{STATS}/{location}/dane-rzadowe#{section}"


def values(result: dict[str, Any]) -> list[float]:
    found = [v for series in result["series"] for v in series["values"] if v is not None]
    assert found, "brak wartości"
    return found


def test_government_average_area_of_poland(polska_area: Call) -> None:
    """The page the user showed: polska#gus-srednia-powierzchnia."""
    result = polska_area.data

    check_statistics(result, "polska", "average_area", "gus-srednia-powierzchnia")
    assert (result["frequency"], result["source"]) == ("year", "GUS")
    assert [s["unit"] for s in result["series"]] == ["m²"]
    assert all(30 <= v <= 150 for v in values(result)), values(result)
    assert polska_area.sent == 1


def test_government_nbp_prices_of_a_city(warszawa_nbp: Call) -> None:
    result = warszawa_nbp.data

    check_statistics(result, "warszawa", "nbp_prices", "nbp")
    assert (result["frequency"], result["source"]) == ("quarter", "NBP")
    assert [s["series_id"] for s in result["series"]] == NBP_SERIES
    assert all(s["unit"] == "PLN/m²" for s in result["series"])
    assert all(3_000 <= v <= 80_000 for v in values(result)), values(result)
    assert warszawa_nbp.sent == 1


def test_government_average_area_of_an_aggregate(aggregate_area: Call) -> None:
    """1 request: an aggregate's page, whose ``citySlug`` is the aggregate's slug and
    ``cityName`` its name [P 2026-10-31, tests/fixtures/rsc/stats_gov_7_miast_20261031.rsc]."""
    result = aggregate_area.data

    check_statistics(result, "7-miast", "average_area", "gus-srednia-powierzchnia")
    assert result["location_name"] != "7-miast"  # the page's name, not the slug
    assert (result["frequency"], result["source"]) == ("year", "GUS")
    assert all(30 <= v <= 150 for v in values(result)), values(result)
    assert aggregate_area.sent == 1


@pytest.mark.parametrize("dataset", ["wages", "unemployment"])
def test_government_an_aggregate_has_no_wages_nor_a_rate_of_its_own(
    mcp: McpLive, aggregate_area: Call, dataset: str
) -> None:
    """[P 2026-10-31] ``7-miast`` lists no wages section, and its unemployment section
    shows each of its cities: not published (the message points to polska and a city),
    never a changed service. From the cache."""
    call = mcp.call("get_government_statistics", location="7-miast", dataset=dataset)

    assert call.error and SERVICE_CHANGED not in call.text, call.text[:200]
    assert call.text.startswith(f"Serwis nie publikuje zestawu {dataset!r}"), call.text[:200]
    assert "polska" in call.text
    from_cache(call)


def test_government_another_dataset_of_the_same_location_comes_from_the_cache(
    mcp: McpLive, polska_area: Call
) -> None:
    """One page per location [P]: unemployment of polska is on the page already read."""
    call = mcp.call("get_government_statistics", location="polska", dataset="unemployment")

    result = call.data
    check_statistics(result, "polska", "unemployment", "gus-bezrobocie")
    assert all(0 <= v <= 40 for v in values(result)), values(result)
    from_cache(call)


def test_government_nbp_prices_of_poland_point_to_cities(mcp: McpLive, polska_area: Call) -> None:
    """[P 2026-10-31] the page of polska has a grid of cities, no NBP series of its own."""
    call = mcp.call("get_government_statistics", location="polska", dataset="nbp_prices")

    assert call.error, f"polska ma własną serię NBP: {call.text[:200]}"
    assert "NBP nie podaje jednej ceny dla całej Polski" in call.text
    assert "7-miast" in call.text and "warszawa" in call.text
    from_cache(call)


def test_government_demography_of_poland_comes_from_eurostat(
    mcp: McpLive, polska_area: Call
) -> None:
    """[P 2026-10-31] monthly births and deaths of Eurostat, in the section the page of
    polska lists for them (``eurostat-demografia``, not ``gus-demografia``). From the
    cache."""
    call = mcp.call("get_government_statistics", location="polska", dataset="demography")

    result = call.data
    check_statistics(result, "polska", "demography", "eurostat-demografia")
    assert (result["frequency"], result["source"]) == ("month", "Eurostat")
    assert [s["series_id"] for s in result["series"]] == ["births", "deaths", "natural_increase"]
    from_cache(call)


def test_government_dwellings_fit_the_size_budget(mcp: McpLive, polska_area: Call) -> None:
    """The widest dataset (15 series) with the default 12 periods."""
    call = mcp.call("get_government_statistics", location="polska", dataset="dwellings_quarterly")

    check_statistics(call.data, "polska", "dwellings_quarterly", "gus-mieszkania")
    assert len(call.data["series"]) >= 14
    assert len(call.text) < SIZE_BUDGET
    from_cache(call)


def test_government_unknown_location(mcp: McpLive) -> None:
    """[P 2026-10-31] the page answers a location it does not know with a 404 whose body
    is a flight stream (``text/x-component``), its own "unknown" (docs/discovery/
    endpoints.md section 9, "Pages"): the tool says what to give, never that the service
    changed (which it would if the adapter's 404 opt-in were not wired)."""
    call = mcp.call_network("get_government_statistics", location=UNKNOWN_LOCATION, dataset="wages")

    assert call.error, f"serwis zna lokalizację {UNKNOWN_LOCATION!r}: {call.text[:200]}"
    assert SERVICE_CHANGED not in call.text, call.text[:200]
    assert call.text.startswith(
        f"Serwis nie ma statystyk rządowych dla lokalizacji {UNKNOWN_LOCATION!r}"
    )
    assert "polska" in call.text and "7-miast" in call.text
    assert call.sent == 1


@pytest.mark.parametrize("dataset", ["average_area", "wages", "dwellings_quarterly"])
def test_government_a_small_city_has_the_page_of_a_city(
    mcp: McpLive, small_city_area: Call, dataset: str
) -> None:
    """[W] every city page has the template of warszawa [P 2026-10-31]: its ``citySlug``,
    the ids of its charts and sections, the keys of its rows. One page (1 request, the
    fixture), then the cache: each dataset is there, or not published, never a change of
    the service. A dataset sopot lacks is a warning, a finding for T74."""
    call = (
        small_city_area
        if dataset == "average_area"
        else mcp.call("get_government_statistics", location=SMALL_CITY, dataset=dataset)
    )

    assert not (call.error and SERVICE_CHANGED in call.text), call.text[:200]
    if call.error:
        assert call.text.startswith(f"Serwis nie publikuje zestawu {dataset!r}"), call.text
        warnings.warn(f"{SMALL_CITY}: brak zestawu {dataset} (ustalenie do T74)", stacklevel=1)
    else:
        check_statistics(call.data, SMALL_CITY, dataset, CITY_SECTIONS[dataset])
    if call is not small_city_area:
        from_cache(call)
    assert small_city_area.sent == 1


def test_government_nbp_prices_of_a_city_without_them(mcp: McpLive, small_city_area: Call) -> None:
    """[W] sopot has no NBP prices (on 1.0 [P 2026-10-11]; on 2.0 it is listed after the
    cities of NBP on the page of polska): its page lists no ``nbp`` section, so the tool
    says where NBP prices are. From the cache."""
    call = mcp.call("get_government_statistics", location=SMALL_CITY, dataset="nbp_prices")

    assert SERVICE_CHANGED not in call.text, call.text[:200]
    if not call.error:
        pytest.xfail(f"Ustalenie: {SMALL_CITY} ma ceny NBP na 2.0 (do T74)")
    assert call.text.startswith(f"NBP nie publikuje cen mieszkań dla lokalizacji {SMALL_CITY!r}")
    assert "7-miast" in call.text and "warszawa" in call.text
    from_cache(call)


def test_government_wages_of_a_city_have_their_ratio_to_the_country(
    mcp: McpLive, warszawa_nbp: Call
) -> None:
    """[P 2026-10-31] the ratio to the national average is read from the notes of the
    yearly wages chart, text of the site's UI (D21): present, 50–400 %. A change of their
    wording drops the series and logs a WARNING (quoted on failure). From the cache (the
    page of ``warszawa_nbp``)."""
    call = mcp.call("get_government_statistics", location="warszawa", dataset="wages")

    result = call.data
    check_statistics(result, "warszawa", "wages", "gus-wynagrodzenia")
    series = {item["series_id"]: item for item in result["series"]}
    logged = [line for line in mcp.log.text().splitlines() if "średniej krajowej" in line]
    assert "relative_to_poland" in series, f"brak relacji do średniej krajowej: {logged[-1:]}"
    ratios = [value for value in series["relative_to_poland"]["values"] if value is not None]
    assert ratios and all(50 <= value <= 400 for value in ratios), ratios
    from_cache(call)


def test_government_nbp_prices_of_another_aggregate(mcp: McpLive) -> None:
    """1 request, [W]: ``10-miast`` has the page of ``7-miast`` [P 2026-10-31], with NBP
    prices (the grid of polska has its series [P 2026-10-31])."""
    call = mcp.call_network("get_government_statistics", location="10-miast", dataset="nbp_prices")

    assert not call.error, call.text[:200]
    result = call.data
    check_statistics(result, "10-miast", "nbp_prices", "nbp")
    assert [item["series_id"] for item in result["series"]] == NBP_SERIES
    assert call.sent == 1


def test_government_a_city_whose_slug_has_a_hyphen(mcp: McpLive) -> None:
    """1 request, [W]: ``jastrzebie-zdroj`` is the slug the 2.0 pages link (``jastrzebie`` on
    1.0) [P 2026-10-31]; its page has the template of ``warszawa``."""
    call = mcp.call_network(
        "get_government_statistics", location="jastrzebie-zdroj", dataset="population"
    )

    assert not call.error, call.text[:200]
    check_statistics(call.data, "jastrzebie-zdroj", "population", CITY_SECTIONS["population"])
    assert call.data["location_name"] != "jastrzebie-zdroj"  # the page's own name
    assert call.sent == 1


def test_government_nbp_prices_of_a_city_outside_the_grid(mcp: McpLive) -> None:
    """1 request, [W]: the text of the page of polska names the NBP price of ``lodz``
    (9945 zł/m² in 2026-Q2), a city outside its grid of six [P 2026-10-31]: its page has an
    NBP series like the page of ``warszawa``."""
    call = mcp.call_network("get_government_statistics", location="lodz", dataset="nbp_prices")

    assert SERVICE_CHANGED not in call.text, call.text[:200]
    assert not call.error, f"Ustalenie: lodz bez cen NBP na 2.0 (do T74): {call.text[:200]}"
    check_statistics(call.data, "lodz", "nbp_prices", "nbp")
    assert call.sent == 1


@pytest.mark.parametrize("location", ["Kraków", "kraków", ""])
def test_government_location_that_is_not_a_slug_is_refused_without_a_request(
    mcp: McpLive, location: str
) -> None:
    call = mcp.call("get_government_statistics", location=location, dataset="wages")

    assert call.error and call.text.startswith("location: oczekiwano polska")
    assert call.sent == 0


def test_the_statistics_link_leads_to_its_section(budget: Budget, polska_area: Call) -> None:
    """1 request (probe): the page of stats_url, without its fragment, lists the section
    the fragment names among its sections. The 2.0 page has no ``tocItems``; its section
    ids are the strings of ``govSections``, which differ per location [P 2026-10-31,
    sample page.stats_gov.v2_sections, tests/fixtures/rsc/stats_gov_*_20261031.rsc].
    --full: probe trims lists on stdout (3 items and a marker string), and the section may
    be past them."""
    page, section = polska_area.data["stats_url"].removeprefix(BASE_URL).split("#")

    run = run_probe(budget, "page", page, "--prop", "govSections", "--full")

    assert run.code == 0, (run.code, run.stderr)
    sections = json.loads(run.stdout)
    assert section in sections, sections


# --- two calls at once -----------------------------------------------------------------


def test_two_calls_at_once_go_one_by_one_through_the_limiter(mcp: McpLive, city_slug: str) -> None:
    """Both succeed; their requests are logged about a second apart (shared limiter)."""
    calls, logged = mcp.parallel(
        ("search_offers", {"city": city_slug, "page": 3}),
        ("search_offers", {"city": "warszawa", "page": 2}),
    )

    for call in calls:
        check_page(call.data, **call.arguments)
    assert len(logged) == 2
    assert logged[1] - logged[0] >= 0.9, logged


# --- 2026-10-13: unknown arguments, new filters and orders, price flags ----------------------


def test_offers_unknown_argument_is_refused_without_a_request(mcp: McpLive, city_slug: str) -> None:
    """A model's typo is refused, naming the argument and the allowed ones (no silent
    search without the limit)."""
    call = mcp.call("search_offers", city=city_slug, max_price=500_000)

    assert call.error
    assert call.text.startswith("Nieznany argument narzędzia search_offers: 'max_price'.")
    assert "price_max" in call.text
    assert call.sent == 0


def mokotow(mokot: dict[str, Any]) -> dict[str, Any]:
    found = [
        item
        for item in mokot["items"]
        if item["kind"] == "district"
        and item["name"] == "Mokotów"
        and item["city_slug"] == "warszawa"
    ]
    assert found, mokot["items"]
    district: dict[str, Any] = found[0]
    return district


def test_offers_in_a_district_cheaper_than_their_first_price(
    mcp: McpLive, mokot: dict[str, Any]
) -> None:
    """[P 2026-10-31] the district's own list, at the slug of the name search_locations
    gives (``mokotow``, [W] the slug), with filterPriceChange=decrease (below the first
    price; [W] on that route, T73): 1 request. The district alone has `offer_count` offers
    [P 2026-10-10], so with the second filter at most that."""
    district = mokotow(mokot)
    arguments = {"district": district["name"], "price_dropped": True}

    call = mcp.call_network("search_offers", city="warszawa", **arguments)

    items = check_page(call.data, "warszawa", **arguments)
    assert call.data["total"] > 0, "brak przecenionych ofert na Mokotowie"
    if "offer_count" in district:
        assert call.data["total"] <= district["offer_count"], (call.data["total"], district)
    changes = [
        i["price_change_since_start_pct"] for i in items if "price_change_since_start_pct" in i
    ]
    assert changes and all(change < 0 for change in changes), changes
    assert call.sent == 1


def test_offers_archived(mcp: McpLive, city_slug: str) -> None:
    """[P 2026-10-31] filterStatus=archived (12,471 in Warszawa; its rows were read on 1.0
    only, [W] on 2.0): only withdrawn offers: 1 request."""
    call = mcp.call_network("search_offers", city=city_slug, status="archived")

    items = check_page(call.data, city_slug, status="archived")
    assert items and all(item["status"] == "archived" for item in items), items[:2]


def test_offers_in_a_price_per_m2_range_by_price_per_m2_descending(
    mcp: McpLive, city_slug: str, first_page: Call
) -> None:
    """filterPricePerM2 narrows the list [P 2026-10-31] and sortBy=price_per_sqm&sortOrder=desc
    orders it ([W], from the UI's code): 1 request. The result's price per m² is price /
    area (to 0.01), the service's to 0.01 too: 1 PLN of slack."""
    arguments = {
        "price_per_m2_min": 12_000,
        "price_per_m2_max": 16_000,
        "sort": "price_per_m2_desc",
    }

    call = mcp.call_network("search_offers", city=city_slug, **arguments)

    result = call.data
    items = check_page(result, city_slug, **arguments)
    values = [item["price_per_m2"] for item in items if "price_per_m2" in item]
    assert values, "brak ofert z ceną za m²"
    assert all(12_000 - 1 <= value <= 16_000 + 1 for value in values), (
        f"Ustalenie [W]: filterPricePerM2 nie zawęża listy (ceny za m²: {values}); "
        "do docs/discovery/pages-rsc.md"
    )
    assert result["total"] < first_page.data["total"], "filtr nie zmniejszył total [W]"
    assert values == sorted(values, reverse=True), (
        f"Ustalenie [W]: sortBy=price_per_sqm&sortOrder=desc nie sortuje malejąco: {values}"
    )


def test_offers_by_area_descending(mcp: McpLive, city_slug: str) -> None:
    """[W] sortBy=size&sortOrder=desc (only ascending is [P]): 1 request."""
    call = mcp.call_network("search_offers", city=city_slug, sort="area_desc")

    areas = [
        i["area_m2"] for i in check_page(call.data, city_slug, sort="area_desc") if "area_m2" in i
    ]
    assert areas and areas == sorted(areas, reverse=True), (
        f"Ustalenie [W]: sortBy=size&sortOrder=desc nie sortuje malejąco: {areas}"
    )


# --- 2026-10-31: the 2.0 offers list ------------------------------------------------------


def ascending(values: list[float], slack: float = 0) -> bool:
    """Each value at least the one before it, less ``slack`` (a rounding of the service)."""
    return all(after >= before - slack for before, after in zip(values, values[1:], strict=False))


def test_offers_in_a_district_of_two_words_with_polish_letters(mcp: McpLive) -> None:
    """[W] the slug the search makes of a district's name: ``Praga-Południe`` is
    ``praga-poludnie`` in the service's links [P 2026-10-31]; its list answers with offers,
    not "no such district": 1 request."""
    arguments = {"district": "Praga-Południe"}

    call = mcp.call_network("search_offers", city="warszawa", **arguments)

    assert not call.error, f"Ustalenie [W]: slug dzielnicy z polskimi znakami: {call.text[:300]}"
    check_page(call.data, "warszawa", **arguments)
    assert call.data["total"] > 0
    assert call.sent == 1


def test_offers_in_a_district_within_ranges_cheapest_first_on_page_2(
    mcp: McpLive, mokot: dict[str, Any]
) -> None:
    """[W] T73: the district's list takes the parameters of the city's list: a price range, a
    lower end of the area, an upper end of the price per m² (the sentinel below), an order
    and page 2. Every offer within the ranges (1 PLN/m² of rounding), cheapest first:
    1 request."""
    district = mokotow(mokot)
    arguments = {
        "district": district["name"],
        "price_min": 600_000,
        "price_max": 1_200_000,
        "area_min": 40,
        "price_per_m2_max": 30_000,
        "sort": "price_asc",
        "page": 2,
    }

    call = mcp.call_network("search_offers", city="warszawa", **arguments)

    result = call.data
    assert result["total"] > 10, f"za mało ofert na stronę 2 przy tych filtrach: {result['total']}"
    items = check_page(result, "warszawa", **arguments)
    values = prices(items)
    assert all(600_000 <= value <= 1_200_000 for value in values), (
        f"Ustalenie [W] T73: filterPrice na liście dzielnicy nie zawęża: {values}"
    )
    assert values == sorted(values), f"Ustalenie [W] T73: sortBy na liście dzielnicy: {values}"
    areas = [item["area_m2"] for item in items if "area_m2" in item]
    assert areas and all(area >= 40 for area in areas), (
        f"Ustalenie [W] T73: filterSize na liście dzielnicy: {areas}"
    )
    per_m2 = [item["price_per_m2"] for item in items if "price_per_m2" in item]
    assert per_m2 and all(value <= 30_000 + 1 for value in per_m2), (
        f"Ustalenie [W] T73: filterPricePerM2 na liście dzielnicy: {per_m2}"
    )
    if "offer_count" in district:
        assert result["total"] <= district["offer_count"], (result["total"], district)


def test_offers_archived_in_a_district_by_area_descending_50_per_page(
    mcp: McpLive, mokot: dict[str, Any]
) -> None:
    """[W] T73: the district's list with filterStatus=archived, sortBy=size&sortOrder=desc
    and perPage=50. If it ignored the status, an archived search would quietly show active
    offers: every row archived, the areas descending: 1 request."""
    district = mokotow(mokot)
    arguments = {
        "district": district["name"],
        "status": "archived",
        "sort": "area_desc",
        "per_page": 50,
    }

    call = mcp.call_network("search_offers", city="warszawa", **arguments)

    items = check_page(call.data, "warszawa", **arguments)
    statuses = {item["status"] for item in items}
    assert items and statuses == {"archived"}, (
        f"Ustalenie [W] T73: filterStatus na liście dzielnicy: {statuses}"
    )
    areas = [item["area_m2"] for item in items if "area_m2" in item]
    assert areas and areas == sorted(areas, reverse=True), (
        f"Ustalenie [W] T73: sortBy=size&sortOrder=desc na liście dzielnicy: {areas}"
    )


def test_offers_in_an_unknown_district_say_so(mcp: McpLive) -> None:
    """[P 2026-10-31] a district the city does not have: 200 with Next.js's 404 marker, read
    as "no such district" with the way to the right name, never as a changed service:
    1 request."""
    call = mcp.call_network("search_offers", city="warszawa", district=UNKNOWN_DISTRICT)

    assert call.error
    assert "nie zna dzielnicy" in call.text and "search_locations (kind=district" in call.text
    assert SERVICE_CHANGED not in call.text
    assert call.sent == 1


def test_offers_with_ranges_open_above_keep_their_starts(mcp: McpLive, city_slug: str) -> None:
    """[W] the UI's ends of an open range (99999999 PLN, 9999 m², 999999 PLN/m²), never sent
    to 2.0 before (T33): ranges with only a start find offers, each from every start. 1 PLN
    of slack for the price per m² (rounding). 1 request."""
    arguments = {"price_min": 800_000, "area_min": 50, "price_per_m2_min": 12_000}

    call = mcp.call_network("search_offers", city=city_slug, **arguments)

    items = check_page(call.data, city_slug, **arguments)
    assert call.data["total"] > 0, "Ustalenie [W] T33: zakresy otwarte z góry nie dają ofert"
    for item in items:
        assert item.get("price", 800_000) >= 800_000, item
        assert item.get("area_m2", 50) >= 50, item
        assert item.get("price_per_m2", 12_000) >= 12_000 - 1, item


@pytest.mark.parametrize(
    ("sort", "field", "slack", "page"),
    [
        ("price_per_m2_asc", "price_per_m2", 1, 1),
        ("area_asc", "area_m2", 0, MAX_PAGES),
        ("biggest_drop", "price_change_since_start_pct", 0, 1),
    ],
)
def test_offers_in_the_other_orders(
    mcp: McpLive, city_slug: str, sort: str, field: str, slack: float, page: int
) -> None:
    """[W] on 2.0 every order but the dearest first [P 2026-10-31] (the descending ones have
    their own tests): ascending by its value, the largest drop first for biggest_drop. By
    area on page 20: [P 2026-10-31] ``totalPages`` stops at 20, so it is the last page
    served, in full (a page above it is refused without a request, above): 1 request each."""
    arguments: dict[str, Any] = {"sort": sort} | ({"page": page} if page > 1 else {})

    call = mcp.call_network("search_offers", city=city_slug, **arguments)

    result = call.data
    values = [item[field] for item in check_page(result, city_slug, **arguments) if field in item]
    assert values and ascending(values, slack), (
        f"Ustalenie [W]: sortBy={SORTS[sort][0]}&sortOrder={SORTS[sort][1]}: {values}"
    )
    if page == MAX_PAGES:
        assert (result["returned"], result["pages_available"]) == (10, MAX_PAGES)


def test_offers_without_a_match_are_an_empty_list(mcp: McpLive, city_slug: str) -> None:
    """[W] a list without a match was never seen on 2.0 (``sales`` empty, ``totalCount`` 0):
    an empty page with its hint, not a changed service: 1 request."""
    call = mcp.call_network("search_offers", city=city_slug, price_min=99_000_000)

    assert not call.error, f"Ustalenie [W]: pusta lista ofert na 2.0: {call.text[:300]}"
    result = call.data
    check_page(result, city_slug, price_min=99_000_000)
    assert (result["total"], result["items"]) == (0, [])
    assert result["hint"].startswith("Brak ofert spełniających kryteria.")


def test_offers_active_and_archived_together(
    mcp: McpLive, city_slug: str, first_page: Call
) -> None:
    """[W] T72: includeArchived=true lists active and archived offers (34,011 in Warszawa
    against 11,672 active and 12,471 with filterStatus=archived, the rest unexplained):
    every row is one of the two, and there are no fewer than the active ones: 1 request."""
    call = mcp.call_network("search_offers", city=city_slug, status="all")

    items = check_page(call.data, city_slug, status="all")
    statuses = {item["status"] for item in items}
    assert items and statuses <= {"active", "archived"}, f"Ustalenie [W] T72: {statuses}"
    assert call.data["total"] >= first_page.data["total"], (call.data["total"], "T72")


def test_offer_price_flags_agree_with_its_history(
    mcp: McpLive, investment: Call, offer: dict[str, Any]
) -> None:
    """The flags of today from the history shown with them; the call repeats the earlier
    get_offer, so it comes from the cache."""
    call = mcp.call(
        "get_offer", offer_id=offer["offer_id"], investment_slug=offer["investment_slug"]
    )

    result = call.data
    flags = result["price_flags"]
    points = [e["price"] for e in result["price_history"] if e["kind"] == "offer" and "price" in e]
    assert isinstance(flags["suspicious_reduction"], bool)
    assert 0 <= flags["price_changes"] <= max(0, len(points) - 1)
    for window in ("lowest_price_30d", "lowest_price_90d"):
        if window in flags:
            assert flags[window] in points, (window, flags, points)
    if "lowest_price_30d" in flags and "lowest_price_90d" in flags:
        assert flags["lowest_price_90d"] <= flags["lowest_price_30d"]
    for pct in ("largest_drop_pct", "largest_rise_pct"):
        assert flags.get(pct, 1) > 0, flags
    from_cache(call)


# --- get_market_statistics (D15, D20) ---------------------------------------------------


@pytest.fixture(scope="module")
def market(mcp: McpLive, city_slug: str) -> Call:
    return mcp.call_network("get_market_statistics", city=city_slug)


def check_spread(spread: dict[str, Any]) -> None:
    values = [spread[key] for key in ("min", "p25", "median", "p75", "max")]
    assert values == sorted(values), spread


def check_as_of(result: dict[str, Any]) -> None:
    """[P 2026-10-31] the snapshot names the day of its data (``asOf``), and Cloudflare may
    serve a copy more than half a day old: a day from yesterday to tomorrow (the service
    may count days in Polish time, ahead of UTC); an older one is a warning."""
    assert "as_of" in result, "wynik bez as_of: snapshot nie podał asOf"
    as_of, today = dt.date.fromisoformat(result["as_of"]), dt.datetime.now(dt.UTC).date()
    assert as_of <= today + dt.timedelta(days=1), (as_of, today)
    if as_of < today - dt.timedelta(days=1):
        warnings.warn(f"as_of {as_of} jest starszy niż wczoraj ({today})", stacklevel=2)


def test_market_of_a_city(market: Call, city_slug: str, first_page: Call) -> None:
    """Every active offer of the city in one request (the offer snapshot), only aggregates
    in the result. [W] the snapshot of a city other than the two captured (sopot,
    warszawa) has their shape: positions read as price and area give plausible medians.
    [P 2026-10-31] it holds active offers only (as many as the list's total the same
    day); the client counts every offer it holds, so a total far off the list's (T72:
    34,011 with the archived ones against 11,672 active) fails, and a small gap (the
    snapshot is a cached copy, hours old) is a warning."""
    result = market.data

    assert result["city_slug"] == city_slug
    check_as_of(result)
    assert 0 < result["investments"] <= result["offers"]
    assert 0 < result["developers"] <= result["investments"]
    for name in ("price", "price_per_m2", "area_m2"):
        check_spread(result[name])
    assert 100_000 < result["price"]["median"] < 5_000_000
    assert 5_000 < result["price_per_m2"]["median"] < 60_000
    assert 20 < result["area_m2"]["median"] < 150
    top = result["top_developers"]
    assert result["developers_returned"] == len(top) == min(10, result["developers"])
    assert result["truncated"] == (result["developers"] > len(top))
    offers = [d["offers"] for d in top]
    assert offers == sorted(offers, reverse=True) and sum(offers) <= result["offers"]
    for share in top:
        assert share["developer_url"] == page_url(city_slug, "deweloperzy", share["developer_slug"])
        assert share.get("developer_name", "").strip(), share  # [P 2026-10-31] every one
    assert result["list_url"] == page_url(city_slug, "mieszkania") + "?perPage=10"
    assert not {"offer_id", "items", "investment_slug"} & keys(result)
    assert len(market.text) < SIZE_BUDGET
    assert market.sent == 1
    total = first_page.data["total"]
    assert abs(result["offers"] - total) <= 0.25 * total, (
        f"{city_slug}: {result['offers']} ofert w statystykach, {total} aktywnych w "
        "search_offers: więcej niż 25% różnicy, snapshot mógł objąć oferty archiwalne"
    )
    if abs(result["offers"] - total) > 0.02 * total:
        warnings.warn(
            f"{city_slug}: {result['offers']} ofert w statystykach ≠ {total} w search_offers "
            "(o więcej niż 2%)",
            stacklevel=1,
        )


def test_market_with_filters(mcp: McpLive, city_slug: str, market: Call) -> None:
    """The same snapshot, narrowed: from the cache, unless its TTL (s-maxage minus Age, at
    most 300 s) ran out (then 1 request)."""
    call = mcp.call("get_market_statistics", city=city_slug, price_max=700_000, area_min=40)

    result = call.data
    assert result["offers"] <= market.data["offers"]
    if result["offers"]:
        assert result["price"]["max"] <= 700_000 and result["area_m2"]["min"] >= 40
    assert result["list_url"].endswith("?filterPrice=0-700000&filterSize=40-9999&perPage=10")
    assert call.sent <= 1


def test_market_of_the_whole_country_is_refused_without_a_request(mcp: McpLive) -> None:
    call = mcp.call("get_market_statistics", city="polska")

    assert call.error and "tylko dla jednego miasta" in call.text
    assert call.sent == 0


def test_market_of_an_unknown_city(mcp: McpLive) -> None:
    """[P 2026-10-31] endpoints.md section 9: the snapshot of a city the service does not
    know is a 404 JSON ``{"error":"Unknown city"}``, which the model reads as "no such
    city", never as a changed service (D21)."""
    call = mcp.call_network("get_market_statistics", city=UNKNOWN_CITY)

    assert call.error and call.text.startswith(f"Serwis nie zna miasta '{UNKNOWN_CITY}'")
    assert "search_locations" in call.text and SERVICE_CHANGED not in call.text
    assert call.sent == 1


# --- get_developer -----------------------------------------------------------------------


def check_developer(result: dict[str, Any], slug: str, city: str, limit: int = 20) -> None:
    assert result["developer"]["developer_slug"] == slug and result["developer"]["name"]
    assert result["developer_url"] == page_url(city, "deweloperzy", slug)
    assert result["city_slug"] == city
    investments = result["investments"]
    returned, omitted = result["investments_returned"], result["investments_omitted"]
    assert returned == len(investments) == min(limit, result["investments_total"])
    assert omitted == result["investments_total"] - returned
    assert result["truncated"] == (omitted > 0)
    active = [item.get("active_offers", 0) for item in investments]
    assert active == sorted(active, reverse=True)
    for item in investments:
        assert item["investment_url"] == page_url(
            item["city_slug"], "deweloperzy", slug, item["investment_slug"]
        )
        assert item.get("active_offers", 0) <= item.get("total_offers", 10**9)
    if not result["truncated"]:
        # The summary sums up the investments (DeveloperProfile.summary, 2.0).
        assert result["summary"].get("active_offers") == sum(active)
    check_cities(result)


def check_cities(result: dict[str, Any]) -> None:
    """[P 2026-10-31] a city's counts come from display text („60”, „1 816”,
    DeveloperCityRowDto._count): every city has both, else the chart changed. The cities
    come by active offers, then by price per m² (DeveloperProfile.listing), and without
    truncation each city of the investments sums them up."""
    cities = result["cities"]
    assert cities and all(SLUG.fullmatch(c["city_slug"]) for c in cities)
    for city in cities:
        assert isinstance(city.get("investments"), int), city
        assert isinstance(city.get("active_offers"), int), city
    order = [(c["active_offers"], c.get("avg_price_per_m2", 0)) for c in cities]
    assert order == sorted(order, reverse=True), order
    if result["truncated"]:
        return
    listed = {c["city_slug"]: c for c in cities}
    for item in result["investments"]:
        assert item.get("city_slug"), f"inwestycja bez city_slug: {item}"
    for city_slug in {item["city_slug"] for item in result["investments"]}:
        mine = [i for i in result["investments"] if i["city_slug"] == city_slug]
        assert city_slug in listed, city_slug
        assert listed[city_slug]["investments"] == len(mine)
        assert listed[city_slug]["active_offers"] == sum(i.get("active_offers", 0) for i in mine)


@pytest.fixture(scope="module")
def developer_of_the_country(mcp: McpLive, offer: dict[str, Any]) -> Call:
    """The developer of the first offer, city=polska by default: 1 request."""
    return mcp.call_network("get_developer", developer_slug=offer["developer_slug"])


def test_developer_of_the_whole_country(
    developer_of_the_country: Call, offer: dict[str, Any], city_slug: str
) -> None:
    """The developer of the first offer in the whole country (fixture)."""
    call = developer_of_the_country

    result = call.data
    check_developer(result, offer["developer_slug"], "polska")
    if city_slug not in {c["city_slug"] for c in result["cities"]}:
        warnings.warn(f"{city_slug!r} nie jest wśród miast dewelopera", stacklevel=1)
    assert len(call.text) < SIZE_BUDGET_DEVELOPER
    assert call.sent == 1


def test_developer_in_a_city(
    mcp: McpLive, offer: dict[str, Any], city_slug: str, developer_of_the_country: Call
) -> None:
    """city=<the offer's city>: its investments only, the offer's among them: 1 request.

    [W] a page without the chart of cities is a developer in one city, so its cities come
    from its investments (DeveloperPageDto.to_model): then the city's page and the
    country's name the same cities, as they do with the chart."""
    slug = offer["developer_slug"]

    call = mcp.call_network("get_developer", developer_slug=slug, city=city_slug, limit=100)

    result = call.data
    check_developer(result, slug, city_slug, limit=100)
    assert {item["city_slug"] for item in result["investments"]} == {city_slug}
    country = {c["city_slug"] for c in developer_of_the_country.data["cities"]}
    assert {c["city_slug"] for c in result["cities"]} == country, (result["cities"], country)
    # [P 2026-10-31] the city's row of the chart is the summary of the city's page; the
    # price per m² within 1 PLN (the summary weighs the investments' rounded figures). A
    # null figure is left out of the result (D11), hence .get.
    (row,) = [c for c in result["cities"] if c["city_slug"] == city_slug]
    summary = result["summary"]
    assert (row.get("investments"), row.get("active_offers")) == (
        result["investments_total"],
        summary.get("active_offers"),
    ), (row, summary)
    row_price, summary_price = row.get("avg_price_per_m2"), summary.get("avg_price_per_m2")
    assert row_price is not None and summary_price is not None, (row, summary)
    assert abs(row_price - summary_price) <= 1, (row, summary)
    if offer["investment_slug"] not in {i["investment_slug"] for i in result["investments"]}:
        warnings.warn(
            f"inwestycji {offer['investment_slug']!r} z wyszukiwania nie ma w profilu "
            f"dewelopera w {city_slug!r}",
            stacklevel=1,
        )
    assert call.sent == 1


def test_developer_unknown(mcp: McpLive) -> None:
    """[P 2026-10-31] the page of an unknown developer answers 200 with Next.js's 404
    marker, for the whole country (the default city here) as for Warsaw (1.0: a heading
    instead): the model reads where slugs come from. The CLI asks for Warsaw."""
    call = mcp.call_network("get_developer", developer_slug=UNKNOWN_DEVELOPER)

    assert call.error and "Nie znaleziono dewelopera" in call.text, call.text[:200]
    assert "search_offers" in call.text and SERVICE_CHANGED not in call.text
    assert call.sent == 1


def test_developer_in_an_unknown_city(mcp: McpLive, offer: dict[str, Any]) -> None:
    """[H] a known developer in an unknown city (T39): "not found" (the 404 marker) or a
    profile without investments (with a hint). Anything else is a finding."""
    call = mcp.call_network(
        "get_developer", developer_slug=offer["developer_slug"], city=UNKNOWN_CITY
    )

    if call.error and "Nie znaleziono dewelopera" in call.text:
        pass
    elif not call.error and call.data["investments_total"] == 0:
        assert "Spróbuj city=polska" in call.data["hint"]
    else:
        pytest.xfail(
            "Ustalenie: profil dewelopera w nieznanym mieście odpowiada inaczej niż "
            f"„nie znaleziono” albo pusty profil (komunikat: {call.text[:160]!r}). Pozycja do "
            "docs/open-questions.md."
        )
    assert call.sent == 1
