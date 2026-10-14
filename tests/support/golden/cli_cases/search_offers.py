"""The golden cases of ``deweloperuch offers search`` (tests/golden/cli/<case>.json)."""

import httpx

from support.builders.offers import offers_page
from support.golden.cli import FILTERS, INJECTED_BODY, NEW_FILTERS, OFFERS, Case, case, offers_fail
from support.golden.routes import offers_answer, offers_page_with, offers_with
from support.providers.routes.offers import offers_route, unknown_city_route
from support.providers.rsc import (
    UNKNOWN_CITY,
)
from support.providers.samples import rsc_payload

CASES: dict[str, Case] = {
    "help_offers_search": case("offers", "search", "--help"),
    # offers search
    "offers_search": case(*OFFERS, "warszawa", service=offers_route),
    "offers_search_json": case(*OFFERS, "warszawa", "--json", service=offers_route),
    "offers_search_every_option": case(
        *OFFERS, "warszawa", *FILTERS, service=offers_with(offers_page("page.offers_list.filtered"))
    ),
    "offers_search_every_option_json": case(
        *OFFERS,
        "warszawa",
        *FILTERS,
        "--json",
        service=offers_with(offers_page("page.offers_list.filtered")),
    ),
    "offers_search_price_max": case(
        *OFFERS, "krakow", "--price-max", "500000", service=offers_route
    ),
    "offers_search_price_min": case(
        *OFFERS, "krakow", "--price-min", "500000", service=offers_route
    ),
    "offers_search_price_zero": case(
        *OFFERS, "krakow", "--price-min", "0", "--price-max", "0", service=offers_route
    ),
    "offers_search_price_limits": case(
        *OFFERS,
        "krakow",
        "--price-min",
        "99999999",
        "--price-max",
        "99999999",
        service=offers_route,
    ),
    "offers_search_area_min": case(*OFFERS, "krakow", "--area-min", "40", service=offers_route),
    "offers_search_area_max": case(*OFFERS, "krakow", "--area-max", "60", service=offers_route),
    "offers_search_area_limits": case(
        *OFFERS, "krakow", "--area-min", "0", "--area-max", "9999", service=offers_route
    ),
    "offers_search_price_and_area": case(
        *OFFERS, "krakow", "--price-max", "900000", "--area-min", "35", service=offers_route
    ),
    "offers_search_sort_asc": case(*OFFERS, "krakow", "--sort", "price_asc", service=offers_route),
    "offers_search_sort_desc": case(
        *OFFERS, "krakow", "--sort", "price_desc", service=offers_route
    ),
    "offers_search_page_20_per_page_100": case(
        *OFFERS,
        "warszawa",
        "--page",
        "20",
        "--per-page",
        "100",
        service=offers_with(offers_page(count=100)),
    ),
    "offers_search_per_page_50": case(
        *OFFERS, "warszawa", "--per-page", "50", service=offers_with(offers_page(count=50))
    ),
    "offers_search_whole_country": case(*OFFERS, "polska", service=offers_route),
    "offers_search_whole_country_json": case(*OFFERS, "polska", "--json", service=offers_route),
    "offers_search_city_with_spaces": case(*OFFERS, " warszawa ", service=offers_route),
    "offers_search_nothing": case(
        *OFFERS, "warszawa", service=offers_with(offers_page_with(0, empty=True))
    ),
    "offers_search_nothing_json": case(
        *OFFERS, "warszawa", "--json", service=offers_with(offers_page_with(0, empty=True))
    ),
    "offers_search_past_the_last_page": case(
        *OFFERS, "warszawa", "--page", "9", service=offers_with(offers_page_with(30, 9, empty=True))
    ),
    "offers_search_not_truncated": case(
        *OFFERS, "warszawa", service=offers_with(offers_page_with(3))
    ),
    "offers_search_truncated_at_100": case(
        *OFFERS,
        "warszawa",
        "--per-page",
        "100",
        service=offers_with(offers_page_with(2001, 1, 100)),
    ),
    "offers_search_exactly_2000": case(
        *OFFERS,
        "warszawa",
        "--per-page",
        "100",
        service=offers_with(offers_page_with(2000, 1, 100)),
    ),
    "offers_search_unknown_city": case(*OFFERS, UNKNOWN_CITY, service=unknown_city_route),
    "offers_search_page_21": case(*OFFERS, "warszawa", "--page", "21", service=offers_route),
    "offers_search_page_0": case(*OFFERS, "warszawa", "--page", "0", service=offers_route),
    "offers_search_city_name": case(*OFFERS, "Kraków", service=offers_route),
    "offers_search_city_capitals": case(*OFFERS, "KRAKOW", service=offers_route),
    "offers_search_city_blank": case(*OFFERS, " ", service=offers_route),
    "offers_search_city_path": case(*OFFERS, "warszawa/../x", service=offers_route),
    "offers_search_price_reversed": case(
        *OFFERS, "warszawa", "--price-min", "7", "--price-max", "5", service=offers_route
    ),
    "offers_search_area_reversed": case(
        *OFFERS, "warszawa", "--area-min", "60", "--area-max", "40", service=offers_route
    ),
    "offers_search_area_negative": case(
        *OFFERS, "warszawa", "--area-min", "-1", service=offers_route
    ),
    "offers_search_price_negative": case(
        *OFFERS, "warszawa", "--price-max", "-1", service=offers_route
    ),
    "offers_search_price_too_big": case(
        *OFFERS, "warszawa", "--price-max", "100000000", service=offers_route
    ),
    "offers_search_area_too_big": case(
        *OFFERS, "warszawa", "--area-max", "10000", service=offers_route
    ),
    "offers_search_sort_unknown": case(*OFFERS, "warszawa", "--sort", "rooms_asc"),
    "offers_search_new_filters": case(*OFFERS, "warszawa", *NEW_FILTERS, service=offers_route),
    "offers_search_new_filters_json": case(
        *OFFERS, "warszawa", *NEW_FILTERS, "--json", service=offers_route
    ),
    "offers_search_status_all": case(*OFFERS, "krakow", "--status", "all", service=offers_route),
    "offers_search_status_unknown": case(*OFFERS, "krakow", "--status", "sold"),
    "offers_search_district_whole_country": case(
        *OFFERS, "polska", "--district", "Mokotów", service=offers_route
    ),
    "offers_search_district_blank": case(
        *OFFERS, "warszawa", "--district", " ", service=offers_route
    ),
    "offers_search_price_per_m2_reversed": case(
        *OFFERS,
        "warszawa",
        "--price-per-m2-min",
        "15000",
        "--price-per-m2-max",
        "9000",
        service=offers_route,
    ),
    "offers_search_per_page_20": case(*OFFERS, "warszawa", "--per-page", "20"),
    "offers_search_page_text": case(*OFFERS, "warszawa", "--page", "two"),
    "offers_search_price_fraction": case(*OFFERS, "warszawa", "--price-max", "1.5"),
    "offers_search_without_city": case(*OFFERS),
    "offers_search_503": case(
        *OFFERS, "warszawa", service=offers_answer(503, headers={"Retry-After": "10"}, text="busy")
    ),
    "offers_search_403": case(*OFFERS, "warszawa", service=offers_answer(403)),
    "offers_search_429": case(
        *OFFERS, "warszawa", service=offers_answer(429, headers={"Retry-After": "300"})
    ),
    "offers_search_page_without_data": case(
        *OFFERS,
        "warszawa",
        service=offers_answer(200, content=rsc_payload({"other": {"text": INJECTED_BODY}})),
    ),
    "offers_search_network_error": case(
        *OFFERS, "warszawa", service=offers_fail(httpx.ConnectError(INJECTED_BODY))
    ),
}
