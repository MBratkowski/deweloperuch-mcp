"""The golden cases of ``deweloperuch stats government`` (tests/golden/cli/<case>.json)."""

from deweloperuch_mcp.models.government_statistics import Dataset
from support.golden.cli import INJECTED_BODY, Case, case
from support.golden.routes import stats_answer
from support.providers.routes.government_statistics import (
    UNKNOWN_LOCATION,
    stats_routes,
    unknown_location_route,
)
from support.providers.rsc import (
    STATS_POLSKA,
    raw,
)
from support.providers.samples import rsc_payload

CASES: dict[str, Case] = {
    "help_stats_government": case("stats", "government", "--help"),
    "stats_government_wroclaw_2_0_wages": case(
        "stats", "government", "wroclaw", "wages", "--periods", "3", service=stats_routes
    ),
    # stats government: the real pages
    **{
        f"stats_{location}_{dataset.value}": case(
            "stats", "government", location, dataset.value, service=stats_routes
        )
        for location in ("polska", "warszawa")
        for dataset in Dataset
    },
    **{
        f"stats_{location}_{dataset.value}_json": case(
            "stats", "government", location, dataset.value, "--json", service=stats_routes
        )
        for location in ("polska", "warszawa")
        for dataset in Dataset
        if (location, dataset) != ("polska", Dataset.NBP_PRICES)
    },
    "stats_warszawa_nbp_prices_2": case(
        "stats", "government", "warszawa", "nbp_prices", "--periods", "2", service=stats_routes
    ),
    "stats_polska_unemployment_1_json": case(
        "stats",
        "government",
        "polska",
        "unemployment",
        "--periods",
        "1",
        "--json",
        service=stats_routes,
    ),
    "stats_polska_dwellings_quarterly_all": case(
        "stats",
        "government",
        "polska",
        "dwellings_quarterly",
        "--periods",
        "1000",
        service=stats_routes,
    ),
    "stats_warszawa_dwellings_monthly_120": case(
        "stats",
        "government",
        "warszawa",
        "dwellings_monthly",
        "--periods",
        "120",
        service=stats_routes,
    ),
    "stats_unknown_location": case(
        "stats", "government", UNKNOWN_LOCATION, "wages", service=unknown_location_route
    ),
    "stats_page_of_another_location": case(
        "stats",
        "government",
        "krakow",
        "wages",
        service=stats_answer("krakow", 200, content=raw(STATS_POLSKA)),
    ),
    "stats_page_without_data": case(
        "stats",
        "government",
        "warszawa",
        "wages",
        service=stats_answer(
            "warszawa", 200, content=rsc_payload({"other": {"text": INJECTED_BODY}})
        ),
    ),
    "stats_503": case(
        "stats",
        "government",
        "warszawa",
        "wages",
        service=stats_answer("warszawa", 503, headers={"Retry-After": "10"}),
    ),
    "stats_403": case(
        "stats", "government", "warszawa", "wages", service=stats_answer("warszawa", 403)
    ),
    "stats_location_capitals": case(
        "stats", "government", "Warszawa", "wages", service=stats_routes
    ),
    "stats_location_polish_letters": case("stats", "government", "kraków", "wages"),
    "stats_location_path": case("stats", "government", "../api/cities", "wages"),
    "stats_periods_0": case("stats", "government", "warszawa", "wages", "--periods", "0"),
    "stats_periods_1001": case("stats", "government", "warszawa", "wages", "--periods", "1001"),
    "stats_periods_text": case("stats", "government", "warszawa", "wages", "--periods", "x"),
    "stats_dataset_unknown": case("stats", "government", "warszawa", "prices"),
    "stats_without_dataset": case("stats", "government", "warszawa"),
}
