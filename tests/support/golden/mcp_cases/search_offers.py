"""The golden cases of the MCP tool ``search_offers`` (tests/golden/mcp/<case>.json)."""

import httpx

from support.builders.offers import offers_page
from support.golden.mcp import FILTERED, INJECTED, OFFERS, WARSZAWA, Case, case
from support.golden.routes import offers_answer, offers_page_with, offers_with
from support.providers.routes.offers import offers_route, unknown_city_route
from support.providers.rsc import UNKNOWN_CITY
from support.providers.samples import rsc_payload

CASES: dict[str, Case] = {
    # search_offers
    "offers": case(OFFERS, offers_route, **WARSZAWA),
    "offers_whole_country": case(OFFERS, offers_route, city="polska"),
    "offers_every_argument": case(
        OFFERS,
        offers_with(FILTERED),
        city="warszawa",
        price_min=500_000,
        price_max=700_000,
        area_min=40,
        area_max=60,
        sort="price_asc",
        page=2,
        per_page=50,
    ),
    "offers_price_min": case(OFFERS, offers_route, city="krakow", price_min=500_000),
    "offers_price_max": case(OFFERS, offers_route, city="krakow", price_max=500_000),
    "offers_price_zero": case(OFFERS, offers_route, city="krakow", price_min=0, price_max=0),
    "offers_area_min": case(OFFERS, offers_route, city="krakow", area_min=40),
    "offers_area_max": case(OFFERS, offers_route, city="krakow", area_max=60),
    "offers_area_limits": case(OFFERS, offers_route, city="krakow", area_min=0, area_max=9999),
    "offers_price_and_area": case(
        OFFERS, offers_route, city="krakow", price_max=900_000, area_min=35
    ),
    "offers_sort_desc": case(OFFERS, offers_route, city="krakow", sort="price_desc"),
    "offers_page_2": case(OFFERS, offers_route, city="warszawa", page=2),
    "offers_per_page_50": case(
        OFFERS, offers_with(offers_page(count=50)), city="warszawa", per_page=50
    ),
    "offers_per_page_text": case(OFFERS, offers_route, city="warszawa", per_page="50"),
    "offers_page_text": case(OFFERS, offers_route, city="warszawa", page="2"),
    "offers_price_min_text": case(OFFERS, offers_route, city="warszawa", price_min="500000"),
    "offers_area_max_text_with_spaces": case(
        OFFERS, offers_route, city="warszawa", area_max=" 60 "
    ),
    "offers_price_min_blank": case(
        OFFERS, offers_route, city="warszawa", price_min="", price_max="700000"
    ),
    "offers_price_max_space": case(OFFERS, offers_route, city="warszawa", price_max=" "),
    "offers_nulls": case(
        OFFERS,
        offers_route,
        city="warszawa",
        price_min=None,
        price_max=None,
        area_min=None,
        area_max=None,
        sort=None,
        page=None,
        per_page=None,
    ),
    "offers_sort_blank": case(OFFERS, offers_route, city="warszawa", sort=""),
    "offers_sort_with_spaces": case(OFFERS, offers_route, city="warszawa", sort=" price_asc "),
    "offers_city_with_spaces": case(OFFERS, offers_route, city=" warszawa "),
    "offers_unknown_argument": case(OFFERS, offers_route, city="warszawa", max_price=500_000),
    "offers_nothing": case(OFFERS, offers_with(offers_page_with(0, empty=True)), **WARSZAWA),
    "offers_past_the_last_page": case(
        OFFERS, offers_with(offers_page_with(30, 9, empty=True)), city="warszawa", page=9
    ),
    "offers_not_truncated": case(OFFERS, offers_with(offers_page_with(3)), **WARSZAWA),
    "offers_unknown_city": case(OFFERS, unknown_city_route, city=UNKNOWN_CITY),
    "offers_city_name": case(OFFERS, offers_route, city="Kraków"),
    "offers_city_capitalized": case(OFFERS, offers_route, city="Warszawa"),
    "offers_city_capitals": case(OFFERS, offers_route, city="KRAKOW"),
    "offers_city_blank": case(OFFERS, offers_route, city=""),
    "offers_city_path": case(OFFERS, offers_route, city="warszawa/../x"),
    "offers_city_null": case(OFFERS, offers_route, city=None),
    "offers_without_city": case(OFFERS, offers_route, per_page=10),
    "offers_price_reversed": case(
        OFFERS, offers_route, city="warszawa", price_min=700_000, price_max=500_000
    ),
    "offers_area_reversed": case(OFFERS, offers_route, city="warszawa", area_min=60, area_max=40),
    "offers_per_page_100": case(OFFERS, offers_route, city="warszawa", per_page=100),
    "offers_per_page_100_text": case(OFFERS, offers_route, city="warszawa", per_page="100"),
    "offers_per_page_20": case(OFFERS, offers_route, city="warszawa", per_page=20),
    "offers_page_21": case(OFFERS, offers_route, city="warszawa", page=21),
    "offers_page_21_and_sort_unknown": case(
        OFFERS, offers_route, city="warszawa", page=21, sort="rooms_asc"
    ),
    "offers_sort_unknown": case(OFFERS, offers_route, city="warszawa", sort="rooms_asc"),
    "offers_new_filters": case(
        OFFERS,
        offers_route,
        city="warszawa",
        price_per_m2_min=12_000,
        price_per_m2_max="20000",
        district="Mokotów",
        price_dropped=True,
        status="archived",
        sort="biggest_drop",
    ),
    "offers_status_all_and_sort_by_area": case(
        OFFERS, offers_route, city="krakow", status="all", sort="area_asc"
    ),
    "offers_district_whole_country": case(OFFERS, offers_route, city="polska", district="Wola"),
    "offers_district_blank_and_nulls": case(
        OFFERS, offers_route, city="warszawa", district=" ", status=None, price_dropped=None
    ),
    "offers_status_unknown": case(OFFERS, offers_route, city="warszawa", status="sold"),
    "offers_price_per_m2_too_big": case(
        OFFERS, offers_route, city="warszawa", price_per_m2_max=1_000_000
    ),
    "offers_unknown_arguments": case(
        OFFERS, offers_route, city="warszawa", rooms=2, floor="1", developer="atal"
    ),
    "offers_price_negative": case(OFFERS, offers_route, city="warszawa", price_max=-1),
    "offers_price_too_big": case(OFFERS, offers_route, city="warszawa", price_max=100_000_000),
    "offers_price_fraction_text": case(OFFERS, offers_route, city="warszawa", price_min="10.5"),
    "offers_price_true": case(OFFERS, offers_route, city="warszawa", price_min=True),
    "offers_area_false": case(OFFERS, offers_route, city="warszawa", area_max=False),
    "offers_page_true": case(OFFERS, offers_route, city="warszawa", page=True),
    "offers_per_page_true": case(OFFERS, offers_route, city="warszawa", per_page=True),
    "offers_price_float_text": case(OFFERS, offers_route, city="warszawa", price_min="500000.0"),
    "offers_page_float_text": case(OFFERS, offers_route, city="warszawa", page="2.0"),
    "offers_per_page_float_text": case(OFFERS, offers_route, city="warszawa", per_page="10.0"),
    "offers_price_words": case(OFFERS, offers_route, city="warszawa", price_min="dużo"),
    "offers_page_blank": case(OFFERS, offers_route, city="warszawa", page=""),
    "offers_503": case(
        OFFERS, offers_answer(503, headers={"Retry-After": "10"}, text="busy"), **WARSZAWA
    ),
    "offers_403": case(OFFERS, offers_answer(403), **WARSZAWA),
    "offers_429": case(OFFERS, offers_answer(429, headers={"Retry-After": "300"}), **WARSZAWA),
    "offers_page_without_data": case(
        OFFERS,
        offers_answer(200, content=rsc_payload({"other": {"text": INJECTED}})),
        **WARSZAWA,
    ),
    "offers_network_error": case(
        OFFERS,
        lambda r: r.route(method="GET", path__startswith="/ceny-ofertowe/").mock(
            side_effect=httpx.ConnectError(INJECTED)
        ),
        **WARSZAWA,
    ),
}
