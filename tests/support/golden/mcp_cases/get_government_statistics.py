"""The golden cases of the MCP tool ``get_government_statistics`` (tests/golden/mcp/<case>.json)."""

from deweloperuch_mcp.models.government_statistics import Dataset
from support.golden.mcp import INJECTED, STATS, Case, case
from support.golden.routes import stats_answer
from support.providers.routes.government_statistics import (
    UNKNOWN_LOCATION,
    stats_routes,
    unknown_location_route,
)
from support.providers.rsc import STATS_POLSKA, raw
from support.providers.samples import rsc_payload

CASES: dict[str, Case] = {
    # get_government_statistics: the real pages
    **{
        f"stats_{location}_{dataset.value}": case(
            STATS, stats_routes, location=location, dataset=dataset.value
        )
        for location in ("polska", "warszawa")
        for dataset in Dataset
    },
    **{
        f"stats_{location}_{dataset.value}_120": case(
            STATS, stats_routes, location=location, dataset=dataset.value, periods=120
        )
        for location in ("polska", "warszawa")
        for dataset in Dataset
        if (location, dataset) != ("polska", Dataset.NBP_PRICES)
    },
    "stats_warszawa_nbp_prices_2": case(
        STATS, stats_routes, location="warszawa", dataset="nbp_prices", periods=2
    ),
    "stats_polska_wages_1": case(
        STATS, stats_routes, location="polska", dataset="wages", periods=1
    ),
    "stats_periods_text": case(
        STATS, stats_routes, location="polska", dataset="wages", periods="3"
    ),
    "stats_periods_text_with_spaces": case(
        STATS, stats_routes, location="polska", dataset="wages", periods=" 5 "
    ),
    "stats_periods_null": case(
        STATS, stats_routes, location="polska", dataset="wages", periods=None
    ),
    "stats_dataset_with_spaces": case(STATS, stats_routes, location="polska", dataset=" wages "),
    "stats_location_with_spaces": case(STATS, stats_routes, location=" polska ", dataset="wages"),
    "stats_two_datasets_one_request": case(
        STATS,
        stats_routes,
        then=((STATS, {"location": "polska", "dataset": "unemployment"}),),
        location="polska",
        dataset="average_area",
    ),
    "stats_unknown_location": case(
        STATS, unknown_location_route, location=UNKNOWN_LOCATION, dataset="wages"
    ),
    "stats_page_of_another_location": case(
        STATS,
        stats_answer("krakow", 200, content=raw(STATS_POLSKA)),
        location="krakow",
        dataset="wages",
    ),
    "stats_page_without_data": case(
        STATS,
        stats_answer("warszawa", 200, content=rsc_payload({"other": {"text": INJECTED}})),
        location="warszawa",
        dataset="wages",
    ),
    "stats_503": case(
        STATS,
        stats_answer("warszawa", 503, headers={"Retry-After": "10"}),
        location="warszawa",
        dataset="wages",
    ),
    "stats_403": case(STATS, stats_answer("warszawa", 403), location="warszawa", dataset="wages"),
    "stats_location_capitalized": case(STATS, stats_routes, location="Warszawa", dataset="wages"),
    "stats_location_polish_letters": case(STATS, stats_routes, location="kraków", dataset="wages"),
    "stats_location_blank": case(STATS, stats_routes, location="", dataset="wages"),
    "stats_location_path": case(STATS, stats_routes, location="a/b", dataset="wages"),
    "stats_location_null": case(STATS, stats_routes, location=None, dataset="wages"),
    "stats_periods_0": case(STATS, stats_routes, location="polska", dataset="wages", periods=0),
    "stats_periods_121": case(STATS, stats_routes, location="polska", dataset="wages", periods=121),
    "stats_periods_true": case(
        STATS, stats_routes, location="polska", dataset="wages", periods=True
    ),
    "stats_periods_float_text": case(
        STATS, stats_routes, location="polska", dataset="wages", periods="3.0"
    ),
    "stats_dataset_unknown": case(STATS, stats_routes, location="polska", dataset="prices"),
    "stats_dataset_null": case(STATS, stats_routes, location="polska", dataset=None),
    "stats_without_dataset": case(STATS, stats_routes, location="polska"),
}
