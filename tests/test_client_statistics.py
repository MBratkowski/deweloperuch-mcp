"""The government statistics page (RSC) and the adapter of its port, on the real pages.

``/statystyki/statystyki-rzadowe/polska`` and ``.../warszawa`` as the service sent them
(tests/fixtures/rsc/stats_gov_*.rsc); edited payloads change one prop value in place,
every other byte stays. Expected values are those the page itself states in its text
(e.g. "16 783 zł/m², II kw. 2026"), so a dataset read from the wrong prop, or a series
from the wrong field, fails here.
"""

import json
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
import respx
from pydantic import ValidationError

from deweloperuch_mcp import identity
from deweloperuch_mcp.allowlist import match_dump, match_page
from deweloperuch_mcp.domain.ports import GovernmentStatisticsSource
from deweloperuch_mcp.domain.statistics import (
    Dataset,
    Frequency,
    LocationStatistics,
    PeriodCount,
    StatisticsTable,
    Unit,
)
from deweloperuch_mcp.domain.values import LocationSlug
from deweloperuch_mcp.errors import (
    SERVICE_CHANGED,
    InvalidInputError,
    NotFoundError,
    UnexpectedResponseError,
)
from deweloperuch_mcp.flight import component_props, error_digests
from deweloperuch_mcp.infrastructure.deweloperuch import dto, rsc
from deweloperuch_mcp.infrastructure.deweloperuch.links import ServicePageLinks
from deweloperuch_mcp.infrastructure.deweloperuch.statistics import (
    MAPPINGS,
    SECTIONS,
    GovernmentStatisticsAdapter,
)
from deweloperuch_mcp.infrastructure.deweloperuch.transport import HttpClient
from deweloperuch_mcp.throttle import RequestLimiter
from discovery_samples import envelope, untrimmed
from rsc_fixtures import (
    OFFERS_UNKNOWN_CITY,
    STATS_FIXTURES,
    STATS_POLSKA,
    STATS_WARSZAWA,
    raw,
    replace_prop,
    rows_with,
    swap_props,
)

BASE = identity.BASE_URL
STATS = BASE + "/statystyki/statystyki-rzadowe"
RSC = {"Content-Type": "text/x-component"}
NOT_FOUND_ROW = b'f:E{"digest":"NEXT_HTTP_ERROR_FALLBACK;404"}\n'


@pytest.fixture
def http(tmp_path: Path) -> Iterator[HttpClient]:
    limiter = RequestLimiter(tmp_path, min_interval=0, testing_only_allow_fast_interval=True)
    with HttpClient(limiter=limiter) as client:
        yield client


@pytest.fixture
def service() -> Iterator[respx.MockRouter]:
    with respx.mock(assert_all_called=False, assert_all_mocked=True) as router:
        yield router


def serve(service: respx.MockRouter, location: str, payload: bytes) -> respx.Route:
    return service.get(path=f"/statystyki/statystyki-rzadowe/{location}").respond(
        200, content=payload, headers=RSC
    )


def published(
    http: HttpClient,
    service: respx.MockRouter,
    location: str,
    payload: bytes | None = None,
    dataset: Dataset = Dataset.AVERAGE_AREA,
) -> LocationStatistics:
    serve(service, location, raw(STATS_FIXTURES[location]) if payload is None else payload)
    return GovernmentStatisticsAdapter(http).location_statistics(LocationSlug(location), dataset)


def values(table: StatisticsTable, series_id: str) -> dict[str, float | None]:
    series = next(s for s in table.series if s.series_id == series_id)
    return {point.period: point.value for point in series.points}


# --- the fixtures themselves ----------------------------------------------------------------------


@pytest.mark.parametrize("path", [STATS_POLSKA, STATS_WARSZAWA])
def test_the_fixtures_are_pages_without_a_404_marker(path: Path) -> None:
    payload = raw(path)

    assert error_digests(payload) == []
    assert b"deweloperuch@" not in payload  # the contact address is redacted
    names = [name for name, value in component_props(payload) if isinstance(value, list)]
    assert names.count("tocItems") == 1 and names.count("sortedLocations") == 1


def test_the_page_has_several_props_called_data() -> None:
    """[P] docs/discovery/pages-rsc.md: "Kilka propsów nazywa się data" (6 and 7)."""
    for path, count in ((STATS_POLSKA, 6), (STATS_WARSZAWA, 7)):
        datas = [v for name, v in component_props(raw(path)) if name == "data"]
        assert len([v for v in datas if isinstance(v, list)]) == count


# --- the request ----------------------------------------------------------------------------------


@pytest.mark.parametrize(("location", "token"), [("polska", "b3d11c70"), ("warszawa", "cc0b509c")])
def test_the_page_is_requested_as_rsc_with_the_token_of_the_fixture(
    http: HttpClient, service: respx.MockRouter, location: str, token: str
) -> None:
    """The same target the fixtures were fetched with (tests/fixtures/rsc/README.md)."""
    route = serve(service, location, raw(STATS_FIXTURES[location]))

    rsc.government_stats(http, location)

    request = route.calls.last.request
    assert str(request.url) == f"{STATS}/{location}?_rsc={token}"
    assert request.headers["rsc"] == "1"
    assert request.headers.get_list("user-agent") == [identity.USER_AGENT]


def test_the_page_is_a_documented_read_channel_and_no_dump() -> None:
    """D1, D5: on the allowlist (pages-rsc.md), not a dump; ~400 KB, far below 32 MiB."""
    path = rsc.government_stats_path("polska")

    assert match_page(path) == "/statystyki/statystyki-rzadowe/{location}"
    assert match_dump(path) is None
    assert max(len(raw(p)) for p in STATS_FIXTURES.values()) < 1024 * 1024


def test_a_location_with_separators_never_reaches_the_service(
    http: HttpClient, service: respx.MockRouter
) -> None:
    with pytest.raises(InvalidInputError):
        rsc.government_stats(http, "../../api/map/powiat-sales/208")

    assert service.calls.call_count == 0


def test_the_adapter_is_the_port(http: HttpClient) -> None:
    source: GovernmentStatisticsSource = GovernmentStatisticsAdapter(http)

    assert callable(source.location_statistics)


# --- what the page has, per location --------------------------------------------------------------


def test_polska_has_every_dataset_but_nbp_prices(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """The whole country shows a grid of cities' NBP prices, not a series of its own."""
    page = published(http, service, "polska")

    assert set(page.tables) == set(Dataset) - {Dataset.NBP_PRICES}
    assert page.name == "Polska"


def test_warszawa_has_every_dataset(http: HttpClient, service: respx.MockRouter) -> None:
    page = published(http, service, "warszawa")

    assert set(page.tables) == set(Dataset)
    assert page.name == "Warszawa"


@pytest.mark.parametrize(
    ("location", "dataset", "frequency", "source", "periods", "first", "last"),
    [
        ("polska", Dataset.DWELLINGS_QUARTERLY, Frequency.QUARTER, "GUS", 87, "2005-Q1", "2026-Q3"),
        ("polska", Dataset.DWELLINGS_MONTHLY, Frequency.MONTH, "GUS", 260, "2005-01", "2026-08"),
        ("polska", Dataset.AVERAGE_AREA, Frequency.YEAR, "GUS", 22, "2005", "2026"),
        ("polska", Dataset.DEMOGRAPHY, Frequency.MONTH, "Eurostat", 357, "1996-01", "2025-09"),
        ("polska", Dataset.POPULATION, Frequency.YEAR, "GUS", 21, "2005", "2025"),
        ("polska", Dataset.UNEMPLOYMENT, Frequency.MONTH, "GUS", 188, "2011-01", "2026-08"),
        ("polska", Dataset.WAGES, Frequency.MONTH, "GUS", 199, "2010-01", "2026-07"),
        (
            "warszawa",
            Dataset.DWELLINGS_QUARTERLY,
            Frequency.QUARTER,
            "GUS",
            87,
            "2005-Q1",
            "2026-Q3",
        ),
        ("warszawa", Dataset.DWELLINGS_MONTHLY, Frequency.MONTH, "GUS", 260, "2005-01", "2026-08"),
        ("warszawa", Dataset.AVERAGE_AREA, Frequency.YEAR, "GUS", 22, "2005", "2026"),
        ("warszawa", Dataset.DEMOGRAPHY, Frequency.YEAR, "GUS", 24, "2002", "2025"),
        ("warszawa", Dataset.POPULATION, Frequency.YEAR, "GUS", 21, "2005", "2025"),
        ("warszawa", Dataset.UNEMPLOYMENT, Frequency.MONTH, "GUS", 188, "2011-01", "2026-08"),
        ("warszawa", Dataset.WAGES, Frequency.YEAR, "GUS", 21, "2005", "2025"),
        ("warszawa", Dataset.NBP_PRICES, Frequency.QUARTER, "NBP", 80, "2006-Q3", "2026-Q2"),
    ],
)
def test_each_dataset_has_its_frequency_source_and_periods(
    http: HttpClient,
    service: respx.MockRouter,
    location: str,
    dataset: Dataset,
    frequency: Frequency,
    source: str,
    periods: int,
    first: str,
    last: str,
) -> None:
    table = published(http, service, location).tables[dataset]

    assert (table.frequency, table.source) == (frequency, source)
    assert (len(table.periods), table.periods[0], table.periods[-1]) == (periods, first, last)


# Values the page states in its own text [P 2026-10-11], or the first rows of its data.
STATED: list[tuple[str, Dataset, str, str, float]] = [
    # "GUS · ŚREDNIA POWIERZCHNIA ... Ostatni rok 62,5 m²" / "56,5 m²", "Pierwszy rok 64,6 m²"
    ("polska", Dataset.AVERAGE_AREA, "average_area", "2026", 62.5),
    ("warszawa", Dataset.AVERAGE_AREA, "average_area", "2026", 56.5),
    ("warszawa", Dataset.AVERAGE_AREA, "average_area", "2005", 64.6),
    # "Ostatni miesiąc 5,8% sierpień 2026" / "1,6%"
    ("polska", Dataset.UNEMPLOYMENT, "rate", "2026-08", 5.8),
    ("warszawa", Dataset.UNEMPLOYMENT, "rate", "2026-08", 1.6),
    # "Ostatni miesiąc 9509 zł" / "Brutto — ostatni rok 11 678 zł", "124,6%" of the average
    ("polska", Dataset.WAGES, "gross", "2026-07", 9509.02),
    ("warszawa", Dataset.WAGES, "gross", "2025", 11677.57),
    ("warszawa", Dataset.WAGES, "relative_to_poland", "2025", 124.6),
    # "Urodzenia żywe 14 439", "Zgony 16 730" (GUS, yearly)
    ("warszawa", Dataset.DEMOGRAPHY, "births", "2025", 14439),
    ("warszawa", Dataset.DEMOGRAPHY, "deaths", "2025", 16730),
    ("warszawa", Dataset.DEMOGRAPHY, "natural_increase", "2025", -2291),
    ("polska", Dataset.DEMOGRAPHY, "births", "1996-01", 36549),
    ("polska", Dataset.DEMOGRAPHY, "deaths", "1996-01", 40895),
    # "wyniosła 37 332 510 osób", "19 305 606" women, "18 026 904 mężczyzn"; Warszawa
    # "1 866 729 osób", "1 003 678", "863 051 mężczyzn"
    ("polska", Dataset.POPULATION, "total", "2025", 37_332_510),
    ("polska", Dataset.POPULATION, "women", "2025", 19_305_606),
    ("polska", Dataset.POPULATION, "men", "2025", 18_026_904),
    ("warszawa", Dataset.POPULATION, "total", "2025", 1_866_729),
    # "Rynek pierwotny – cena transakcyjna 16 783 zł/m² II kw. 2026", "Rynek wtórny – cena
    # transakcyjna 16 723", "Pierwotny – cena ofertowa 18 488", "Wtórny – cena ofertowa
    # 19 059"; "III kw. 2006 ... na rynku pierwotnym ... 5605 zł/m²"
    ("warszawa", Dataset.NBP_PRICES, "primary_transaction", "2026-Q2", 16783),
    ("warszawa", Dataset.NBP_PRICES, "secondary_transaction", "2026-Q2", 16723),
    ("warszawa", Dataset.NBP_PRICES, "primary_asking", "2026-Q2", 18488),
    ("warszawa", Dataset.NBP_PRICES, "secondary_asking", "2026-Q2", 19059),
    ("warszawa", Dataset.NBP_PRICES, "primary_transaction", "2006-Q3", 5605),
    # first rows of the data (sample page.stats_gov of 2026-10-09 has the same for warszawa)
    ("warszawa", Dataset.DWELLINGS_QUARTERLY, "completed_total", "2005-Q1", 2755),
    ("warszawa", Dataset.DWELLINGS_QUARTERLY, "completed_developer", "2005-Q1", 1840),
    ("warszawa", Dataset.DWELLINGS_QUARTERLY, "started_total", "2005-Q1", 3245),
    ("warszawa", Dataset.DWELLINGS_QUARTERLY, "started_social", "2005-Q1", 146),
    ("polska", Dataset.DWELLINGS_QUARTERLY, "completed_individual", "2005-Q1", 15377),
    ("polska", Dataset.DWELLINGS_QUARTERLY, "started_for_rent", "2026-Q3", 22),
    ("polska", Dataset.DWELLINGS_MONTHLY, "completed_total", "2026-08", 18145),
    ("polska", Dataset.DWELLINGS_MONTHLY, "started_developer", "2026-08", 10467),
    ("warszawa", Dataset.DWELLINGS_MONTHLY, "completed_total", "2005-01", 1386),
]


@pytest.mark.parametrize(("location", "dataset", "series_id", "period", "value"), STATED)
def test_series_hold_the_values_the_page_states(
    http: HttpClient,
    service: respx.MockRouter,
    location: str,
    dataset: Dataset,
    series_id: str,
    period: str,
    value: float,
) -> None:
    table = published(http, service, location).tables[dataset]

    assert values(table, series_id)[period] == value


def test_series_have_the_units_of_their_dataset(
    http: HttpClient, service: respx.MockRouter
) -> None:
    page = published(http, service, "warszawa")

    units = {(d, s.series_id): s.unit for d, t in page.tables.items() for s in t.series}
    assert units[(Dataset.AVERAGE_AREA, "average_area")] is Unit.SQUARE_METRES
    assert units[(Dataset.NBP_PRICES, "primary_asking")] is Unit.PLN_PER_M2
    assert units[(Dataset.WAGES, "gross")] is Unit.PLN
    assert units[(Dataset.WAGES, "relative_to_poland")] is Unit.PERCENT
    assert units[(Dataset.UNEMPLOYMENT, "rate")] is Unit.PERCENT
    assert units[(Dataset.POPULATION, "total")] is Unit.PEOPLE
    assert units[(Dataset.DWELLINGS_QUARTERLY, "completed_total")] is Unit.DWELLINGS


def test_the_quarters_are_the_sums_of_their_months(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """[P] for every quarter and series of both pages: hence the note on the last one."""
    for location in ("polska", "warszawa"):
        page = published(http, service, location)
        quarterly = page.tables[Dataset.DWELLINGS_QUARTERLY]
        monthly = page.tables[Dataset.DWELLINGS_MONTHLY]
        for series in quarterly.series:
            months = values(monthly, series.series_id)
            for point in series.points:
                year, number = point.period.split("-Q")
                first = 3 * (int(number) - 1) + 1
                parts = [months.get(f"{year}-{m:02d}") for m in range(first, first + 3)]
                known = [v for v in parts if v is not None]
                assert point.value == (sum(known) if known else None), (series, point)


def test_dwellings_for_rent_are_missing_before_2019(
    http: HttpClient, service: respx.MockRouter
) -> None:
    table = published(http, service, "polska").tables[Dataset.DWELLINGS_QUARTERLY]

    rent = values(table, "started_for_rent")
    assert all(rent[p] is None for p in rent if p < "2019-Q1")
    assert all(rent[p] is not None for p in rent if p >= "2019-Q1")


def test_population_total_is_women_plus_men(http: HttpClient, service: respx.MockRouter) -> None:
    table = published(http, service, "warszawa").tables[Dataset.POPULATION]

    women, men, total = (values(table, s) for s in ("women", "men", "total"))
    assert all(total[p] == women[p] + men[p] for p in total)  # type: ignore[operator]


def test_wages_of_the_whole_country_have_no_ratio_to_it(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """Monthly wages (polska) have no ratio: the series is left out, not a list of nulls."""
    table = published(http, service, "polska").tables[Dataset.WAGES]

    assert [s.series_id for s in table.series] == ["gross"]


def test_the_list_of_locations(http: HttpClient, service: respx.MockRouter) -> None:
    """69 locations [P]: 3 aggregates, 66 cities; NBP for 17 cities and the aggregates.
    ``polska`` (the root page) and the documented ``9-miast`` are not on it."""
    locations = published(http, service, "polska").locations

    slugs = [loc.slug for loc in locations]
    assert len(slugs) == 69 and len(set(slugs)) == 69
    assert slugs[:4] == ["7-miast", "10-miast", "6-miast-bez-warszawy", "warszawa"]
    assert [loc.slug for loc in locations if loc.is_aggregate] == slugs[:3]
    assert len([loc for loc in locations if loc.has_nbp_prices]) == 20
    assert "polska" not in slugs and "9-miast" not in slugs
    by_slug = {loc.slug: loc for loc in locations}
    assert by_slug["jastrzebie"].name == "Jastrzębie-Zdrój"
    assert by_slug["7-miast"].name == "Top 7 miast Polski"
    assert by_slug["krakow"].has_nbp_prices and not by_slug["sopot"].has_nbp_prices


# --- links to the sections (D12) ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("location", "dataset", "section"),
    [
        ("polska", Dataset.AVERAGE_AREA, "gus-srednia-powierzchnia"),
        ("polska", Dataset.DEMOGRAPHY, "eurostat-demografia"),
        ("warszawa", Dataset.DEMOGRAPHY, "gus-demografia"),
        ("warszawa", Dataset.NBP_PRICES, "nbp"),
        ("warszawa", Dataset.DWELLINGS_MONTHLY, "gus-mieszkania"),
        ("polska", Dataset.POPULATION, "gus-wiek"),
    ],
)
def test_each_table_links_to_its_section_of_the_page(
    http: HttpClient, service: respx.MockRouter, location: str, dataset: Dataset, section: str
) -> None:
    """The table names its section; the links adapter turns it into the page's anchor."""
    table = published(http, service, location).tables[dataset]

    assert table.section == section
    link = ServicePageLinks().government_statistics(LocationSlug(location), table.section)
    assert link == f"{STATS}/{location}#{section}"


@pytest.mark.parametrize("location", ["polska", "warszawa"])
def test_every_linked_section_is_in_the_table_of_contents(location: str) -> None:
    """The fragments are ids of the page's own table of contents [P]."""
    toc = next(v for n, v in component_props(raw(STATS_FIXTURES[location])) if n == "tocItems")
    ids = {item["id"] for item in toc}

    for dataset, sections in SECTIONS.items():
        if location == "polska" and dataset is Dataset.NBP_PRICES:
            assert not set(sections) & ids and "nbp-grid" in ids
            continue
        assert len(set(sections) & ids) == 1, (dataset, ids)


# --- telling the `data` props apart by their rows -------------------------------------------------


def data_kinds(payload: bytes) -> list[str]:
    """The data props of a page in document order, each named by a key of its rows."""
    marks = ("averageSizeM2", "rate", "brutto", "zgony", "totalKobiety", "pierwotnyOfertowa")
    return [
        next((mark for mark in marks if rows_with(mark)(value)), "?")
        for name, value in component_props(payload)
        if name == "data" and isinstance(value, list)
    ]


def test_datasets_are_recognized_by_their_rows_not_their_order(
    http: HttpClient, service: respx.MockRouter, tmp_path: Path
) -> None:
    """Regression: the area and the unemployment props swapped in the real page give the
    same tables (a parser that went by position would swap the datasets)."""
    payload = raw(STATS_WARSZAWA)
    swapped = swap_props(payload, "data", rows_with("averageSizeM2"), rows_with("rate"))
    before, after = data_kinds(payload), data_kinds(swapped)
    assert before.index("averageSizeM2") < before.index("rate")
    assert after.index("rate") < after.index("averageSizeM2")

    route = serve(service, "warszawa", payload)
    location = LocationSlug("warszawa")
    original = GovernmentStatisticsAdapter(http).location_statistics(location, Dataset.AVERAGE_AREA)
    route.respond(200, content=swapped, headers=RSC)
    limiter = RequestLimiter(
        tmp_path / "other", min_interval=0, testing_only_allow_fast_interval=True
    )
    with HttpClient(limiter=limiter) as fresh:  # its own cache: the edited page is read
        adapter = GovernmentStatisticsAdapter(fresh)
        edited = adapter.location_statistics(location, Dataset.AVERAGE_AREA)

    assert route.calls.last.response.content == swapped
    assert service.calls.call_count == 2
    assert edited.tables == original.tables
    assert values(edited.tables[Dataset.AVERAGE_AREA], "average_area")["2026"] == 56.5
    assert values(edited.tables[Dataset.UNEMPLOYMENT], "rate")["2026-08"] == 1.6


def test_a_dataset_whose_rows_changed_is_unreadable_but_the_others_are_not(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """A renamed field: the page still lists the section, so it is a change of the
    service, not a dataset the location lacks; the other datasets still work."""
    payload = raw(STATS_WARSZAWA)
    area = next(
        v for n, v in component_props(payload) if n == "data" and rows_with("averageSizeM2")(v)
    )
    renamed = [{"year": r["year"], "avgSizeM2": r["averageSizeM2"]} for r in area]
    edited = replace_prop(payload, "data", rows_with("averageSizeM2"), renamed)

    serve(service, "warszawa", edited)
    adapter = GovernmentStatisticsAdapter(http)
    with pytest.raises(UnexpectedResponseError) as caught:
        adapter.location_statistics(LocationSlug("warszawa"), Dataset.AVERAGE_AREA)
    other = adapter.location_statistics(LocationSlug("warszawa"), Dataset.UNEMPLOYMENT)

    assert SERVICE_CHANGED in str(caught.value) and "average_area" in str(caught.value)
    assert "tocItems" not in str(caught.value) and "gus-srednia" not in str(caught.value)
    assert caught.value.detail is not None and "gus-srednia-powierzchnia" in caught.value.detail
    assert Dataset.AVERAGE_AREA not in other.tables and Dataset.UNEMPLOYMENT in other.tables
    assert service.calls.call_count == 1  # the page was valid: the cache kept it


def test_every_row_must_have_the_keys_of_its_dataset(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """Rows are recognized by all of them, not by the first: one row without the area
    makes that dataset unreadable, and only that one."""
    payload = raw(STATS_WARSZAWA)
    area = next(
        v for n, v in component_props(payload) if n == "data" and rows_with("averageSizeM2")(v)
    )
    broken = [*area[:-1], {"year": area[-1]["year"], "avgSizeM2": area[-1]["averageSizeM2"]}]
    edited = replace_prop(payload, "data", rows_with("averageSizeM2"), broken)

    serve(service, "warszawa", edited)
    adapter = GovernmentStatisticsAdapter(http)
    with pytest.raises(UnexpectedResponseError, match="nieczytelne"):
        adapter.location_statistics(LocationSlug("warszawa"), Dataset.AVERAGE_AREA)
    other = adapter.location_statistics(LocationSlug("warszawa"), Dataset.UNEMPLOYMENT)

    assert Dataset.UNEMPLOYMENT in other.tables


def test_two_props_with_rows_of_one_dataset_are_ambiguous(
    http: HttpClient, service: respx.MockRouter
) -> None:
    payload = raw(STATS_WARSZAWA)
    area = next(
        v for n, v in component_props(payload) if n == "data" and rows_with("averageSizeM2")(v)
    )
    doubled = replace_prop(payload, "data", rows_with("rate"), area)

    with pytest.raises(UnexpectedResponseError, match="niejednoznaczne") as caught:
        published(http, service, "warszawa", doubled)

    assert caught.value.detail is not None and "average_area" in caught.value.detail


def test_rows_that_fit_two_datasets_are_ambiguous(
    http: HttpClient, service: respx.MockRouter
) -> None:
    payload = raw(STATS_WARSZAWA)
    area = next(
        v for n, v in component_props(payload) if n == "data" and rows_with("averageSizeM2")(v)
    )
    both = [dict(r, month="2025-01", rate=1.0) for r in area]
    edited = replace_prop(payload, "data", rows_with("averageSizeM2"), both)

    with pytest.raises(UnexpectedResponseError, match="niejednoznaczne"):
        published(http, service, "warszawa", edited)


def test_a_period_twice_is_inconsistent_data(http: HttpClient, service: respx.MockRouter) -> None:
    payload = raw(STATS_WARSZAWA)
    area = next(
        v for n, v in component_props(payload) if n == "data" and rows_with("averageSizeM2")(v)
    )
    edited = replace_prop(payload, "data", rows_with("averageSizeM2"), [*area, area[-1]])

    with pytest.raises(UnexpectedResponseError, match="niespójne"):
        published(http, service, "warszawa", edited)


def test_rows_out_of_order_are_sorted(http: HttpClient, service: respx.MockRouter) -> None:
    payload = raw(STATS_WARSZAWA)
    area = next(
        v for n, v in component_props(payload) if n == "data" and rows_with("averageSizeM2")(v)
    )
    edited = replace_prop(payload, "data", rows_with("averageSizeM2"), area[::-1])

    table = published(http, service, "warszawa", edited).tables[Dataset.AVERAGE_AREA]

    assert table.periods == tuple(str(year) for year in range(2005, 2027))


# --- isolation: one dataset's data never makes another unreadable (the port's contract) -----------


def rows_of(payload: bytes, prop: str, key: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = next(
        v for n, v in component_props(payload) if n == prop and rows_with(key)(v)
    )
    return rows


def dwellings_without(payload: bytes, key: str) -> bytes:
    """The quarterly and monthly dwellings of the real page, ``key`` taken out of every row."""
    for prop, period in (("data", "quarter"), ("monthlyData", "month")):
        rows = next(
            v
            for n, v in component_props(payload)
            if n == prop and rows_with(period)(v) and rows_with("oddane")(v)
        )
        trimmed = [{k: v for k, v in row.items() if k != key} for row in rows]
        payload = replace_prop(payload, prop, dwellings_rows(prop, period), trimmed)
    return payload


def test_a_form_missing_from_the_dwellings_breaks_nothing(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """(a) A key outside the shape gone from every dwellings row (a city that does not
    list one form): unemployment reads as before, and the dwellings themselves only lose
    that series."""
    edited = dwellings_without(raw(STATS_POLSKA), "oddaneZakladowe")
    assert b'"oddaneZakladowe"' not in edited

    page = published(http, service, "polska", edited, Dataset.UNEMPLOYMENT)

    assert values(page.tables[Dataset.UNEMPLOYMENT], "rate")["2026-08"] == 5.8
    dwellings = page.tables[Dataset.DWELLINGS_QUARTERLY]
    ids = [series.series_id for series in dwellings.series]
    assert "completed_company" not in ids and "completed_developer" in ids


@pytest.mark.parametrize(
    "broken",
    [
        {"oddane": "dużo"},  # a value off the contract
        {"quarter": "2025-Q9"},  # a period label off the contract
    ],
)
def test_rows_off_the_contract_in_another_dataset_break_nothing(
    http: HttpClient, service: respx.MockRouter, broken: dict[str, Any]
) -> None:
    """(a') Any defect of the dwellings rows stays there: unemployment reads as before."""
    payload = raw(STATS_POLSKA)
    rows = rows_of(payload, "data", "quarter")
    edited = replace_prop(payload, "data", lambda v: v == rows, [dict(rows[0], **broken)])

    page = published(http, service, "polska", edited, Dataset.UNEMPLOYMENT)

    assert Dataset.UNEMPLOYMENT in page.tables
    assert Dataset.DWELLINGS_QUARTERLY not in page.tables


def test_an_inconsistent_table_of_another_dataset_breaks_nothing(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """(b) A period twice in the unemployment rows: the area reads as before. Kills the
    mutant that re-raises for every dataset."""
    payload = raw(STATS_POLSKA)
    rate = rows_of(payload, "data", "rate")
    edited = replace_prop(payload, "data", rows_with("rate"), [*rate, rate[-1]])

    page = published(http, service, "polska", edited, Dataset.AVERAGE_AREA)

    assert values(page.tables[Dataset.AVERAGE_AREA], "average_area")["2026"] == 62.5
    assert Dataset.UNEMPLOYMENT not in page.tables


@pytest.mark.parametrize(
    ("edit", "match"),
    [("twice", "niespójne"), ("off the contract", "kontrakt")],
)
def test_the_dataset_asked_for_still_fails(
    http: HttpClient, service: respx.MockRouter, edit: str, match: str
) -> None:
    """(c) The same defects in the dataset asked for: a change of the service, said so."""
    payload = raw(STATS_POLSKA)
    rate = rows_of(payload, "data", "rate")
    rows = [*rate, rate[-1]] if edit == "twice" else [dict(rate[0], rate="dużo")]
    edited = replace_prop(payload, "data", rows_with("rate"), rows)

    with pytest.raises(UnexpectedResponseError, match=match) as caught:
        published(http, service, "polska", edited, Dataset.UNEMPLOYMENT)

    assert SERVICE_CHANGED in str(caught.value)
    assert caught.value.detail is not None and "unemployment_monthly" in caught.value.detail


def dwellings_rows(prop: str, period: str) -> Callable[[Any], bool]:
    return lambda value: rows_with(period)(value) and rows_with("oddane")(value)


@pytest.mark.parametrize(
    ("removed", "asked", "kept"),
    [
        (("monthlyData", "month"), Dataset.DWELLINGS_MONTHLY, Dataset.DWELLINGS_QUARTERLY),
        (("data", "quarter"), Dataset.DWELLINGS_QUARTERLY, Dataset.DWELLINGS_MONTHLY),
    ],
)
def test_dwellings_of_one_frequency_alone_leave_the_other_unpublished(
    http: HttpClient,
    service: respx.MockRouter,
    removed: tuple[str, str],
    asked: Dataset,
    kept: Dataset,
) -> None:
    """The section ``gus-mieszkania`` is shared: listed for the frequency the page has, it
    says nothing of the other, which is "not published" (fix the call), not a change of
    the service (stop)."""
    prop, period = removed
    edited = replace_prop(raw(STATS_POLSKA), prop, dwellings_rows(prop, period), [])

    page = published(http, service, "polska", edited, asked)

    assert asked not in page.tables and kept in page.tables
    with pytest.raises(NotFoundError, match=f"^Serwis nie publikuje zestawu '{asked.value}'"):
        page.statistics(asked, PeriodCount())


def test_dwellings_listed_without_any_of_their_data_are_unreadable(
    http: HttpClient, service: respx.MockRouter
) -> None:
    payload = raw(STATS_POLSKA)
    edited = replace_prop(payload, "data", dwellings_rows("data", "quarter"), [])
    edited = replace_prop(edited, "monthlyData", dwellings_rows("monthlyData", "month"), [])

    with pytest.raises(UnexpectedResponseError, match="nieczytelne"):
        published(http, service, "polska", edited, Dataset.DWELLINGS_MONTHLY)


def test_population_without_one_half_has_no_total(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """The total is women plus men, or nothing: a year without the men has no total
    (never the women alone), and the women stay."""
    payload = raw(STATS_POLSKA)
    rows = rows_of(payload, "data", "totalKobiety")
    last = dict(rows[-1], totalMezczyzni=None)
    edited = replace_prop(payload, "data", rows_with("totalKobiety"), [*rows[:-1], last])

    table = published(http, service, "polska", edited, Dataset.POPULATION).tables[
        Dataset.POPULATION
    ]

    year = str(last["year"])
    assert values(table, "total")[year] is None
    assert values(table, "women")[year] == float(last["totalKobiety"])
    assert values(table, "men")[year] is None
    earlier = str(rows[-2]["year"])
    assert values(table, "total")[earlier] == float(
        rows[-2]["totalKobiety"] + rows[-2]["totalMezczyzni"]
    )


@pytest.mark.parametrize(
    ("row", "problem"),
    [
        ({"year": 2025, "averageSizeM2": "61.5"}, None),  # numbers as text are fine
        ({"year": "2025", "averageSizeM2": 61.5}, None),
        ({"year": 1850, "averageSizeM2": 61.5}, "year"),
        ({"year": True, "averageSizeM2": 61.5}, "year"),
        ({"year": 2025, "averageSizeM2": "dużo"}, "averageSizeM2"),
    ],
)
def test_values_are_checked_and_tolerated_like_the_rest_of_the_client(
    http: HttpClient, service: respx.MockRouter, row: dict[str, Any], problem: str | None
) -> None:
    edited = replace_prop(raw(STATS_WARSZAWA), "data", rows_with("averageSizeM2"), [row])

    if problem is None:
        table = published(http, service, "warszawa", edited).tables[Dataset.AVERAGE_AREA]
        assert values(table, "average_area") == {"2025": 61.5}
        return
    with pytest.raises(UnexpectedResponseError, match="kontrakt") as caught:
        published(http, service, "warszawa", edited)
    assert caught.value.detail is not None and problem in caught.value.detail


@pytest.mark.parametrize(
    ("key", "label"),
    [("quarter", "2025-Q5"), ("quarter", "2025Q1"), ("month", "2025-13"), ("month", "25-01")],
)
def test_period_labels_are_checked(
    http: HttpClient, service: respx.MockRouter, key: str, label: str
) -> None:
    prop = "monthlyData" if key == "month" else "data"
    dataset = Dataset.DWELLINGS_MONTHLY if key == "month" else Dataset.DWELLINGS_QUARTERLY
    payload = raw(STATS_WARSZAWA)
    rows = next(
        v
        for n, v in component_props(payload)
        if n == prop and rows_with(key)(v) and rows_with("oddane")(v)
    )
    edited = replace_prop(payload, prop, lambda v: v == rows, [dict(rows[0], **{key: label})])

    with pytest.raises(UnexpectedResponseError, match="kontrakt"):
        published(http, service, "warszawa", edited, dataset)
    other = GovernmentStatisticsAdapter(http).location_statistics(
        LocationSlug("warszawa"), Dataset.AVERAGE_AREA
    )
    assert dataset not in other.tables and Dataset.AVERAGE_AREA in other.tables


# --- a page that is not the one asked for ---------------------------------------------------------


def test_a_page_with_nextjs_404_marker_is_not_found(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """A real 404 frame of the same app (the offers list of an unknown city). Whether
    the statistics page answers an unknown location this way is [H] (live suite)."""
    serve(service, "nieistniejaca-lokalizacja", raw(OFFERS_UNKNOWN_CITY))

    with pytest.raises(NotFoundError) as caught:
        rsc.government_stats(http, "nieistniejaca-lokalizacja")

    assert caught.value.detail == (
        "/statystyki/statystyki-rzadowe/nieistniejaca-lokalizacja: brak propsa 'tocItems', "
        "strona zgłasza NEXT_HTTP_ERROR_FALLBACK;404"
    )


def test_a_page_without_data_nor_404_marker_is_unexpected(
    http: HttpClient, service: respx.MockRouter
) -> None:
    payload = raw(OFFERS_UNKNOWN_CITY)
    assert payload.count(NOT_FOUND_ROW) == 1
    serve(service, "nieistniejaca-lokalizacja", payload.replace(NOT_FOUND_ROW, b""))

    with pytest.raises(UnexpectedResponseError) as caught:
        rsc.government_stats(http, "nieistniejaca-lokalizacja")

    assert SERVICE_CHANGED in str(caught.value)
    assert caught.value.detail is not None and "tocItems" in caught.value.detail


@pytest.mark.parametrize(("served", "asked"), [("polska", "krakow"), ("warszawa", "polska")])
def test_the_page_of_another_location_is_unexpected(
    http: HttpClient, service: respx.MockRouter, served: str, asked: str
) -> None:
    """A page for another location (e.g. ``polska`` served for an unknown city, [H]) is
    never returned as the asked one's: ``currentSlug`` must be the location (null for
    ``polska`` [P])."""
    serve(service, asked, raw(STATS_FIXTURES[served]))

    with pytest.raises(UnexpectedResponseError, match="innej lokalizacji") as caught:
        rsc.government_stats(http, asked)

    assert caught.value.detail is not None and "currentSlug" in caught.value.detail


def test_a_page_without_its_location_is_unexpected(
    http: HttpClient, service: respx.MockRouter
) -> None:
    edited = raw(STATS_WARSZAWA).replace(b'"currentSlug":"warszawa"', b'"slug":"warszawa"')
    assert b'"currentSlug"' not in edited

    with pytest.raises(UnexpectedResponseError, match="innej lokalizacji"):
        published(http, service, "warszawa", edited)


def test_the_page_served_as_html_is_read_from_its_scripts(
    http: HttpClient, service: respx.MockRouter
) -> None:
    push = json.dumps(raw(STATS_WARSZAWA).decode(), ensure_ascii=False)
    html = f"<!DOCTYPE html><html><script>self.__next_f.push([1,{push}])</script></html>"
    service.get(path="/statystyki/statystyki-rzadowe/warszawa").respond(
        200, content=html.encode(), headers={"Content-Type": "text/html; charset=utf-8"}
    )

    page = GovernmentStatisticsAdapter(http).location_statistics(
        LocationSlug("warszawa"), Dataset.NBP_PRICES
    )

    assert values(page.tables[Dataset.NBP_PRICES], "primary_transaction")["2026-Q2"] == 16783


# --- the sample of the discovery docs -------------------------------------------------------------


def stats_sample() -> dict[str, Any]:
    props: dict[str, Any] = untrimmed(envelope("page.stats_gov")["props"])
    return props


def test_the_sample_parses_with_the_page_dto() -> None:
    """docs/discovery/samples/page.stats_gov.json (warszawa, 2026-10-09): its `data` has
    the rows of quarterly dwellings, its `monthlyData` those of monthly ones."""
    props = stats_sample()

    parsed = dto.GovernmentStatsPageDto.model_validate(
        {
            "tocItems": props["tocItems"],
            "sortedLocations": props["sortedLocations"],
            "dwellings_quarterly": props["data"],
            "dwellings_monthly": props["monthlyData"],
        }
    )
    quarters = dto.validate_rows(dto.DwellingsQuarterDto, parsed.dwellings_quarterly, "sample")
    months = dto.validate_rows(dto.DwellingsMonthDto, parsed.dwellings_monthly, "sample")

    assert [item.id for item in parsed.tocItems] == [
        "gus-mieszkania",
        "gus-formy-budownictwa",
        "gus-srednia-powierzchnia",
    ]
    assert [loc.slug for loc in parsed.sortedLocations] == [
        "7-miast",
        "10-miast",
        "6-miast-bez-warszawy",
    ]
    assert (quarters[0].quarter, quarters[0].oddane) == ("2005-Q1", 2755)
    assert months[0].month.startswith("20")
    shapes = {shape.field: shape for shape in rsc.STATS_SHAPES}
    assert all(shapes["dwellings_quarterly"].keys <= set(row) for row in props["data"])
    assert all(shapes["dwellings_monthly"].keys <= set(row) for row in props["monthlyData"])


def test_the_page_dto_refuses_the_trimming_markers() -> None:
    props = envelope("page.stats_gov")["props"]

    with pytest.raises(ValidationError):
        dto.GovernmentStatsPageDto.model_validate(
            {"tocItems": props["tocItems"], "dwellings_quarterly": props["data"]}
        )
    with pytest.raises(UnexpectedResponseError, match="kontrakt"):
        dto.validate_rows(dto.DwellingsQuarterDto, [*props["data"][:3], {"x": 1}], "sample")


def test_every_data_field_has_its_row() -> None:
    fields = set(dto.GovernmentStatsPageDto.model_fields) - {"tocItems", "sortedLocations"}

    assert set(dto.STATS_ROWS) == fields


def test_every_shape_has_keys_no_other_shape_of_another_group_has_all_of() -> None:
    """No row of one dataset can fit another dataset's shape on its own keys."""
    for shape in rsc.STATS_SHAPES:
        for other in rsc.STATS_SHAPES:
            if other.group != shape.group:
                assert not other.keys <= shape.keys, (shape.field, other.field)


def test_shapes_fields_and_mappings_agree() -> None:
    """Each recognized prop has a field in the page DTO and a mapping to one dataset; the
    shapes of one group map to the same dataset (one table per dataset and page)."""
    shapes = {shape.field: shape for shape in rsc.STATS_SHAPES}
    fields = set(dto.GovernmentStatsPageDto.model_fields) - {"tocItems", "sortedLocations"}
    mappings = {mapping.field: mapping for mapping in MAPPINGS}

    assert set(shapes) == fields == set(mappings)
    for field, shape in shapes.items():
        same_group = [f for f, other in shapes.items() if other.group == shape.group]
        assert {mappings[f].dataset for f in same_group} == {mappings[field].dataset}
    assert {mapping.dataset for mapping in MAPPINGS} == set(Dataset) == set(SECTIONS)
