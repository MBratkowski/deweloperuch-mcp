"""Contract of ``deweloperuch_mcp.api.adapters.government_statistics_api`` with the
service's real answers: the 2.0 pages of 2026-10-31 (tests/fixtures/rsc/
stats_gov_*_20261031.rsc) and the answers of docs/discovery/endpoints.md section 9.
"""

import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import respx

from deweloperuch_mcp import identity
from deweloperuch_mcp.allowlist import match_dump, match_page
from deweloperuch_mcp.api.adapters.government_statistics_api import (
    KNOWN_LOCATIONS,
    GovernmentStatisticsApi,
)
from deweloperuch_mcp.api.http.transport import HttpClient
from deweloperuch_mcp.api.links import ServicePageLinks
from deweloperuch_mcp.errors import (
    SERVICE_CHANGED,
    InvalidInputError,
    NotFoundError,
    UnexpectedResponseError,
)
from deweloperuch_mcp.flight import component_props
from deweloperuch_mcp.models.government_statistics import (
    Dataset,
    Frequency,
    LocationStatistics,
    PeriodCount,
    StatisticsTable,
    Unit,
)
from deweloperuch_mcp.models.values import LocationSlug
from deweloperuch_mcp.throttle import RequestLimiter
from deweloperuch_mcp.usecases.ports import GovernmentStatisticsSource
from support.providers.error_answers import (
    CHANGED_SERVICE,
    removed_route,
    unknown_location_page,
)
from support.providers.routes.government_statistics import STATS_PAGES, stats_path
from support.providers.rsc import (
    OFFERS_UNKNOWN_CITY_20261031,
    raw,
    replace_prop,
    rows_with,
    swap_props,
)
from support.providers.service import BASE

RSC = {"Content-Type": "text/x-component"}

POLSKA, WARSZAWA = raw(STATS_PAGES["polska"]), raw(STATS_PAGES["warszawa"])

WAGES_CHART = "gus-wynagrodzenia-roczne-wykres"

GOV_SECTIONS_OF_WARSZAWA = [
    "gus-mieszkania",
    "gus-formy-budownictwa",
    "gus-srednia-powierzchnia",
    "gus-demografia",
    "gus-wiek",
    "gus-bezrobocie",
    "gus-wynagrodzenia",
    "nbp",
]


def serve(service: respx.MockRouter, location: str, payload: bytes) -> respx.Route:
    return service.get(path=stats_path(location)).respond(200, content=payload, headers=RSC)


def published(
    http: HttpClient,
    service: respx.MockRouter,
    location: str,
    payload: bytes | None = None,
    dataset: Dataset = Dataset.AVERAGE_AREA,
) -> LocationStatistics:
    serve(service, location, raw(STATS_PAGES[location]) if payload is None else payload)
    return GovernmentStatisticsApi(http).location_statistics(LocationSlug(location), dataset)


def values(table: StatisticsTable, series_id: str) -> dict[str, float | None]:
    series = next(s for s in table.series if s.series_id == series_id)
    return {point.period: point.value for point in series.points}


def chart(chart_id: str) -> Callable[[Any], bool]:
    """A prop value that is the chart spec ``chart_id``."""
    return lambda value: isinstance(value, dict) and value.get("id") == chart_id


def spec_of(payload: bytes, chart_id: str) -> dict[str, Any]:
    found: dict[str, Any] = next(v for _, v in component_props(payload) if chart(chart_id)(v))
    return found


def rows_of(payload: bytes, prop: str, key: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = next(
        v for n, v in component_props(payload) if n == prop and rows_with(key)(v)
    )
    return rows


def dwellings_rows(period: str) -> Callable[[Any], bool]:
    return lambda value: rows_with(period)(value) and rows_with("oddane")(value)


def dwellings_without(payload: bytes, key: str) -> bytes:
    """The quarterly and monthly dwellings of the real page, ``key`` taken out of every row."""
    for prop, period in (("data", "quarter"), ("monthlyData", "month")):
        rows = rows_of(payload, prop, period)
        trimmed = [{k: v for k, v in row.items() if k != key} for row in rows]
        payload = replace_prop(payload, prop, dwellings_rows(period), trimmed)
    return payload


def with_points(payload: bytes, chart_id: str, key: str, points: list[Any]) -> bytes:
    """The real page with the points of one dataset of a chart replaced."""
    spec = spec_of(payload, chart_id)
    datasets = {**spec["datasets"], key: {**spec["datasets"][key], "points": points}}
    return replace_prop(payload, "spec", chart(chart_id), {**spec, "datasets": datasets})


def wage_points() -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = spec_of(WARSZAWA, WAGES_CHART)["datasets"][""]["points"]
    return points


# Values the pages state in their own text [P 2026-10-31], or the first rows of their data.
STATED: list[tuple[str, Dataset, str, str, float]] = [
    # "średnia powierzchnia ... w Polsce ... wyniosła 62,5 m²"
    ("polska", Dataset.AVERAGE_AREA, "average_area", "2026", 62.5),
    # "W wrzesień 2025 w Polsce urodziło się 22 500 dzieci, a zmarło 33 000 osób. Przyrost
    # naturalny w tym miesiącu wyniósł -10 500" (Eurostat)
    ("polska", Dataset.DEMOGRAPHY, "births", "2025-09", 22500),
    ("polska", Dataset.DEMOGRAPHY, "deaths", "2025-09", 33000),
    ("polska", Dataset.DEMOGRAPHY, "natural_increase", "2025-09", -10500),
    # "populacja w Polsce wyniosła 37 332 510 osób - 19 305 606 kobiet ... 18 026 904 mężczyzn"
    ("polska", Dataset.POPULATION, "total", "2025", 37_332_510),
    ("polska", Dataset.POPULATION, "women", "2025", 19_305_606),
    ("polska", Dataset.POPULATION, "men", "2025", 18_026_904),
    # "w sierpniu 2026 w Polsce stopa bezrobocia rejestrowanego wyniosła 5,8%"
    ("polska", Dataset.UNEMPLOYMENT, "rate", "2026-08", 5.8),
    # "W sierpniu 2026 przeciętne wynagrodzenie brutto ... wyniosło 9260 zł"
    ("polska", Dataset.WAGES, "gross", "2026-08", 9259.54),
    # "w Warszawie odnotowano 14 439 urodzeń żywych ... i 16 730 zgonów. Przyrost naturalny
    # wyniósł -2291 osób"
    ("warszawa", Dataset.DEMOGRAPHY, "births", "2025", 14439),
    ("warszawa", Dataset.DEMOGRAPHY, "deaths", "2025", 16730),
    ("warszawa", Dataset.DEMOGRAPHY, "natural_increase", "2025", -2291),
    # "populacja w Warszawie wyniosła 1 866 729 osób - 1 003 678 kobiet ... 863 051 mężczyzn"
    ("warszawa", Dataset.POPULATION, "total", "2025", 1_866_729),
    ("warszawa", Dataset.POPULATION, "women", "2025", 1_003_678),
    ("warszawa", Dataset.POPULATION, "men", "2025", 863_051),
    # "w sierpniu 2026 w Warszawie stopa bezrobocia rejestrowanego wyniosła 1,6%"
    ("warszawa", Dataset.UNEMPLOYMENT, "rate", "2026-08", 1.6),
    # "wynagrodzenie brutto w Warszawie wyniosło 11 678 zł ... stanowią 124,6% średniej
    # krajowej"
    ("warszawa", Dataset.WAGES, "gross", "2025", 11677.57),
    ("warszawa", Dataset.WAGES, "relative_to_poland", "2025", 124.6),
    # "na rynku pierwotnym w Warszawie wynosi 16 783 zł/m² ... Na rynku wtórnym mediana to
    # 16 723 zł/m² ... III kw. 2006, gdy m² na rynku pierwotnym kosztowało średnio 5605 zł/m²"
    ("warszawa", Dataset.NBP_PRICES, "primary_transaction", "2026-Q2", 16783),
    ("warszawa", Dataset.NBP_PRICES, "secondary_transaction", "2026-Q2", 16723),
    ("warszawa", Dataset.NBP_PRICES, "primary_transaction", "2006-Q3", 5605),
    # "w 7 największych miastach w Polsce odnotowano 39 772 urodzeń żywych ... i 52 565
    # zgonów. Przyrost naturalny wyniósł -12 793 osób"
    ("7-miast", Dataset.DEMOGRAPHY, "births", "2025", 39772),
    ("7-miast", Dataset.DEMOGRAPHY, "deaths", "2025", 52565),
    ("7-miast", Dataset.DEMOGRAPHY, "natural_increase", "2025", -12793),
    # "populacja w 7 największych miastach w Polsce wyniosła 5 258 113 osób - 2 810 551
    # kobiet ... 2 447 562 mężczyzn"
    ("7-miast", Dataset.POPULATION, "total", "2025", 5_258_113),
    ("7-miast", Dataset.POPULATION, "women", "2025", 2_810_551),
    ("7-miast", Dataset.POPULATION, "men", "2025", 2_447_562),
    # "na rynku pierwotnym w 7 największych miastach w Polsce wynosi 14 444 zł/m² ... Na
    # rynku wtórnym mediana to 13 657 zł/m²"
    ("7-miast", Dataset.NBP_PRICES, "primary_transaction", "2026-Q2", 14444),
    ("7-miast", Dataset.NBP_PRICES, "secondary_transaction", "2026-Q2", 13657),
    # the first rows of the data, as on 1.0 (the sample page.stats_gov of 2026-10-09 has
    # the same for warszawa)
    ("warszawa", Dataset.AVERAGE_AREA, "average_area", "2005", 64.6),
    ("warszawa", Dataset.WAGES, "relative_to_poland", "2005", 144.1),
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


# --- the request ---------------------------------------------------------------------------


@pytest.mark.parametrize("location", list(STATS_PAGES))
def test_the_page_is_requested_as_rsc_with_an_empty_rsc(
    http: HttpClient, service: respx.MockRouter, location: str
) -> None:
    """The 2.0 route, with ``RSC: 1`` and an empty ``_rsc`` (T63, resolved 2026-10-31); the
    1.0 route ``/statystyki/statystyki-rzadowe/{location}`` answers 308 [P 2026-10-29]."""
    route = serve(service, location, raw(STATS_PAGES[location]))

    GovernmentStatisticsApi(http).statistics_page(LocationSlug(location))

    request = route.calls.last.request
    assert str(request.url) == f"{BASE}/statystyki/{location}/dane-rzadowe?_rsc="
    assert request.headers["rsc"] == "1"
    assert request.headers.get_list("user-agent") == [identity.USER_AGENT]


def test_the_page_is_a_documented_read_channel_and_no_dump() -> None:
    """D1, D5: on the allowlist (pages-rsc.md), not a dump; ~0.6 MB at most, below 32 MiB."""
    path = GovernmentStatisticsApi.path("polska")

    assert path == "/statystyki/polska/dane-rzadowe"
    assert match_page(path) == "/statystyki/{location}/dane-rzadowe"
    assert match_dump(path) is None
    assert max(len(raw(p)) for p in STATS_PAGES.values()) < 1024 * 1024


@pytest.mark.parametrize("location", ["../../api/map/powiat-sales/208", "a/b"])
def test_a_location_with_separators_never_reaches_the_service(
    http: HttpClient, service: respx.MockRouter, location: str
) -> None:
    with pytest.raises(InvalidInputError):
        GovernmentStatisticsApi(http).statistics_page(LocationSlug(location))

    assert service.calls.call_count == 0


def test_the_adapter_is_the_port(http: HttpClient) -> None:
    source: GovernmentStatisticsSource = GovernmentStatisticsApi(http)

    assert callable(source.location_statistics)


# --- what each page has --------------------------------------------------------------------


@pytest.mark.parametrize(
    ("location", "missing", "name"),
    [
        ("warszawa", set(), "Warszawa"),
        ("polska", {Dataset.NBP_PRICES}, "Polska"),
        ("7-miast", {Dataset.WAGES, Dataset.UNEMPLOYMENT}, "Top 7 miast Polski"),
    ],
)
def test_the_datasets_each_location_has(
    http: HttpClient, service: respx.MockRouter, location: str, missing: set[Dataset], name: str
) -> None:
    """``polska`` shows a grid of cities' NBP prices, not a series of its own; ``7-miast``
    has no wages, and the unemployment of each of its cities but none of its own
    [P 2026-10-31]: not published (fix the call), never unreadable (stop)."""
    pages = [published(http, service, location, dataset=dataset) for dataset in Dataset]

    assert all(set(page.tables) == set(Dataset) - missing for page in pages)
    assert {page.name for page in pages} == {name}
    for dataset in missing:
        with pytest.raises(NotFoundError, match="nie (publikuje|podaje)"):
            pages[0].statistics(dataset, PeriodCount())


@pytest.mark.parametrize(
    ("location", "dataset", "frequency", "source", "periods", "first", "last"),
    [
        ("polska", Dataset.DWELLINGS_QUARTERLY, Frequency.QUARTER, "GUS", 87, "2005-Q1", "2026-Q3"),
        ("polska", Dataset.DWELLINGS_MONTHLY, Frequency.MONTH, "GUS", 260, "2005-01", "2026-08"),
        ("polska", Dataset.AVERAGE_AREA, Frequency.YEAR, "GUS", 22, "2005", "2026"),
        ("polska", Dataset.DEMOGRAPHY, Frequency.MONTH, "Eurostat", 357, "1996-01", "2025-09"),
        ("polska", Dataset.POPULATION, Frequency.YEAR, "GUS", 21, "2005", "2025"),
        ("polska", Dataset.UNEMPLOYMENT, Frequency.MONTH, "GUS", 188, "2011-01", "2026-08"),
        ("polska", Dataset.WAGES, Frequency.MONTH, "GUS", 200, "2010-01", "2026-08"),
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
        (
            "7-miast",
            Dataset.DWELLINGS_QUARTERLY,
            Frequency.QUARTER,
            "GUS",
            87,
            "2005-Q1",
            "2026-Q3",
        ),
        ("7-miast", Dataset.DWELLINGS_MONTHLY, Frequency.MONTH, "GUS", 260, "2005-01", "2026-08"),
        ("7-miast", Dataset.AVERAGE_AREA, Frequency.YEAR, "GUS", 22, "2005", "2026"),
        ("7-miast", Dataset.DEMOGRAPHY, Frequency.YEAR, "GUS", 31, "1995", "2025"),
        ("7-miast", Dataset.POPULATION, Frequency.YEAR, "GUS", 21, "2005", "2025"),
        ("7-miast", Dataset.NBP_PRICES, Frequency.QUARTER, "NBP", 80, "2006-Q3", "2026-Q2"),
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
    """The demography of ``polska`` is Eurostat's: its chart's ``source`` and the heading of
    its section say so [P 2026-10-31]."""
    table = published(http, service, location).tables[dataset]

    assert (table.frequency, table.source) == (frequency, source)
    assert (len(table.periods), table.periods[0], table.periods[-1]) == (periods, first, last)


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
    assert units[(Dataset.DEMOGRAPHY, "natural_increase")] is Unit.PEOPLE
    assert units[(Dataset.DWELLINGS_QUARTERLY, "completed_total")] is Unit.DWELLINGS


@pytest.mark.parametrize("location", list(STATS_PAGES))
def test_the_quarters_are_the_sums_of_their_months(
    http: HttpClient, service: respx.MockRouter, location: str
) -> None:
    """[P] for every quarter and series of the three pages: hence the note on the last one."""
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


@pytest.mark.parametrize("location", list(STATS_PAGES))
def test_the_natural_increase_is_births_less_deaths(
    http: HttpClient, service: respx.MockRouter, location: str
) -> None:
    """The two datasets of a demography chart, joined by period, agree with each other."""
    table = published(http, service, location).tables[Dataset.DEMOGRAPHY]

    births, deaths, increase = (values(table, s) for s in ("births", "deaths", "natural_increase"))
    assert set(births) == set(increase)
    assert all(increase[p] == births[p] - deaths[p] for p in increase)  # type: ignore[operator]


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


def test_the_unemployment_of_a_city_is_its_own_rate_not_the_countrys(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """The chart of ``warszawa`` also has the national rate (``polska``) for comparison."""
    table = published(http, service, "warszawa").tables[Dataset.UNEMPLOYMENT]

    assert [s.series_id for s in table.series] == ["rate"]
    assert values(table, "rate")["2026-08"] == 1.6  # the national rate is 5.8


def test_wages_of_the_whole_country_have_no_ratio_to_it(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """Monthly wages (polska) have no ratio: the series is left out, not a list of nulls."""
    table = published(http, service, "polska").tables[Dataset.WAGES]

    assert [s.series_id for s in table.series] == ["gross"]


def test_the_ratio_of_the_wages_is_read_from_their_notes(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """Every year has its ratio [P 2026-10-31]; a note in another form is no value."""
    points = wage_points()
    odd = [dict(points[0], notes=["144,1 procent"]), *points[1:]]
    edited = with_points(WARSZAWA, WAGES_CHART, "", odd)

    table = published(http, service, "warszawa", edited, Dataset.WAGES).tables[Dataset.WAGES]

    ratio = values(table, "relative_to_poland")
    assert len(ratio) == 21 and ratio["2005"] is None and ratio["2025"] == 124.6


def test_wages_without_their_notes_keep_the_gross_wage(
    http: HttpClient, service: respx.MockRouter
) -> None:
    edited = with_points(WARSZAWA, WAGES_CHART, "", [dict(p, notes=[]) for p in wage_points()])

    table = published(http, service, "warszawa", edited, Dataset.WAGES).tables[Dataset.WAGES]

    assert [s.series_id for s in table.series] == ["gross"]


def test_wages_with_no_list_of_notes_keep_the_gross_wage(
    http: HttpClient, service: respx.MockRouter, caplog: pytest.LogCaptureFixture
) -> None:
    """``notes: null`` is no ratio, and no change of the service: only the ratio's source
    is read, and only from a list of texts."""
    edited = with_points(WARSZAWA, WAGES_CHART, "", [dict(p, notes=None) for p in wage_points()])

    table = published(http, service, "warszawa", edited, Dataset.WAGES).tables[Dataset.WAGES]

    assert [s.series_id for s in table.series] == ["gross"]
    assert not caplog.records


def test_notes_of_another_form_are_logged(
    http: HttpClient, service: respx.MockRouter, caplog: pytest.LogCaptureFixture
) -> None:
    """Text notes of which none is a ratio: their wording changed. The series is left out
    (the gross wage stays) and a WARNING says so, for the log of the server."""
    edited = with_points(
        WARSZAWA, WAGES_CHART, "", [dict(p, notes=["144,1 procent"]) for p in wage_points()]
    )

    table = published(http, service, "warszawa", edited, Dataset.WAGES).tables[Dataset.WAGES]

    assert [s.series_id for s in table.series] == ["gross"]
    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    assert len(warnings) == 1
    assert WAGES_CHART in warnings[0].getMessage()
    assert "relacją do średniej krajowej" in warnings[0].getMessage()


def test_a_note_with_more_than_the_ratio_is_no_ratio(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """The whole note is the ratio, or it is none (``fullmatch``)."""
    points = wage_points()
    more = [dict(points[0], notes=["144,1\xa0% średniej krajowej (szacunek)"]), *points[1:]]
    edited = with_points(WARSZAWA, WAGES_CHART, "", more)

    table = published(http, service, "warszawa", edited, Dataset.WAGES).tables[Dataset.WAGES]

    assert values(table, "relative_to_poland")["2005"] is None
    assert values(table, "relative_to_poland")["2006"] == 143.7


def test_a_series_the_client_does_not_read_does_not_matter(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """The national rate on the unemployment chart of a city (``polska``) set to "n/d":
    only the values the client reads are checked."""
    points = spec_of(WARSZAWA, "gus-bezrobocie-wykres")["datasets"][""]["points"]
    odd = [dict(p, values={**p["values"], "polska": "n/d"}) for p in points]
    edited = with_points(WARSZAWA, "gus-bezrobocie-wykres", "", odd)

    table = published(http, service, "warszawa", edited, Dataset.UNEMPLOYMENT).tables[
        Dataset.UNEMPLOYMENT
    ]

    assert values(table, "rate")["2026-08"] == 1.6


def test_a_value_the_client_reads_is_checked(http: HttpClient, service: respx.MockRouter) -> None:
    points = spec_of(WARSZAWA, "gus-bezrobocie-wykres")["datasets"][""]["points"]
    odd = [dict(points[0], values={**points[0]["values"], "miejsce": "dużo"}), *points[1:]]
    edited = with_points(WARSZAWA, "gus-bezrobocie-wykres", "", odd)

    with pytest.raises(UnexpectedResponseError, match="kontrakt") as caught:
        published(http, service, "warszawa", edited, Dataset.UNEMPLOYMENT)

    assert caught.value.detail is not None and "miejsce" in caught.value.detail


# --- the sections: the anchors of the links ------------------------------------------------


@pytest.mark.parametrize(
    ("location", "dataset", "section"),
    [
        ("polska", Dataset.AVERAGE_AREA, "gus-srednia-powierzchnia"),
        ("polska", Dataset.DEMOGRAPHY, "eurostat-demografia"),
        ("polska", Dataset.POPULATION, "gus-wiek"),
        ("polska", Dataset.WAGES, "gus-wynagrodzenia"),
        ("warszawa", Dataset.DEMOGRAPHY, "gus-demografia"),
        ("warszawa", Dataset.NBP_PRICES, "nbp"),
        ("warszawa", Dataset.DWELLINGS_MONTHLY, "gus-mieszkania"),
        ("7-miast", Dataset.DEMOGRAPHY, "gus-demografia"),
        ("7-miast", Dataset.NBP_PRICES, "nbp"),
        ("7-miast", Dataset.DWELLINGS_QUARTERLY, "gus-mieszkania"),
    ],
)
def test_each_table_links_to_its_section_of_the_page(
    http: HttpClient, service: respx.MockRouter, location: str, dataset: Dataset, section: str
) -> None:
    """The table names the section its page lists, which the links adapter turns into the
    anchor of ``/statystyki/{location}/dane-rzadowe``."""
    table = published(http, service, location).tables[dataset]

    assert table.section == section
    link = ServicePageLinks().government_statistics(LocationSlug(location), table.section)
    assert link == f"{BASE}/statystyki/{location}/dane-rzadowe#{section}"


@pytest.mark.parametrize("location", list(STATS_PAGES))
def test_no_table_links_to_a_section_its_page_does_not_list(
    http: HttpClient, service: respx.MockRouter, location: str
) -> None:
    """E.g. ``nbp`` or ``gus-demografia`` are no sections of ``polska``."""
    page = published(http, service, location)
    sections = {n: v for n, v in component_props(raw(STATS_PAGES[location])) if n == "blocks"}

    listed = set(sections["blocks"]["govSections"])
    assert {table.section for table in page.tables.values()} <= listed


def test_a_table_whose_section_the_page_does_not_list_has_no_anchor(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """A dataset shown under another id than its own (a renamed section): its data, linked
    to the page without a fragment."""
    edited = POLSKA.replace(b'"eurostat-demografia",', b'"demografia",', 1)
    assert edited.count(b'"demografia",') == 1

    table = published(http, service, "polska", edited, Dataset.DEMOGRAPHY).tables[
        Dataset.DEMOGRAPHY
    ]

    assert table.section is None
    link = ServicePageLinks().government_statistics(LocationSlug("polska"), table.section)
    assert link == f"{BASE}/statystyki/polska/dane-rzadowe"


# --- telling the data apart ---------------------------------------------------------------------


def test_rows_are_recognized_by_their_keys_not_their_order(
    http: HttpClient, service: respx.MockRouter, tmp_path: Path
) -> None:
    """Regression: the population and the NBP props swapped in the real page give the same
    tables (a parser that went by position would swap the datasets)."""
    swapped = swap_props(
        WARSZAWA, "data", rows_with("totalKobiety"), rows_with("pierwotnyOfertowa")
    )
    route = serve(service, "warszawa", WARSZAWA)
    location = LocationSlug("warszawa")
    original = GovernmentStatisticsApi(http).location_statistics(location, Dataset.POPULATION)
    route.respond(200, content=swapped, headers=RSC)
    limiter = RequestLimiter(
        tmp_path / "other", min_interval=0, testing_only_allow_fast_interval=True
    )
    with HttpClient(limiter=limiter) as fresh:  # its own cache: the edited page is read
        edited = GovernmentStatisticsApi(fresh).location_statistics(location, Dataset.POPULATION)

    assert route.calls.last.response.content == swapped
    assert service.calls.call_count == 2
    assert edited.tables == original.tables


def test_charts_are_recognized_by_their_id_not_their_order(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """The area chart and the unemployment chart swapped in place: the same tables."""
    area, rate = (
        spec_of(WARSZAWA, c) for c in ("gus-powierzchnia-wykres", "gus-bezrobocie-wykres")
    )
    swapped = swap_props(WARSZAWA, "spec", chart(area["id"]), chart(rate["id"]))

    page = published(http, service, "warszawa", swapped)

    assert values(page.tables[Dataset.AVERAGE_AREA], "average_area")["2026"] == 56.5
    assert values(page.tables[Dataset.UNEMPLOYMENT], "rate")["2026-08"] == 1.6


def test_a_chart_whose_id_is_no_text_is_left_out(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """Only charts the client knows are kept; any other ``spec`` is no data of a dataset."""
    edited = WARSZAWA.replace(b'"id":"gus-formy-wykres"', b'"id":["gus-formy-wykres"]', 1)
    assert edited != WARSZAWA

    page = published(http, service, "warszawa", edited)

    assert set(page.tables) == set(Dataset)


def test_a_dataset_whose_rows_changed_is_unreadable_but_the_others_are_not(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """A renamed field: the page still lists the section, so it is a change of the
    service, not a dataset the location lacks; the other datasets still work."""
    rows = rows_of(WARSZAWA, "data", "totalKobiety")
    renamed = [{"year": r["year"], "kobiety": r["totalKobiety"]} for r in rows]
    edited = replace_prop(WARSZAWA, "data", rows_with("totalKobiety"), renamed)

    serve(service, "warszawa", edited)
    adapter = GovernmentStatisticsApi(http)
    with pytest.raises(UnexpectedResponseError) as caught:
        adapter.location_statistics(LocationSlug("warszawa"), Dataset.POPULATION)
    other = adapter.location_statistics(LocationSlug("warszawa"), Dataset.UNEMPLOYMENT)

    assert SERVICE_CHANGED in str(caught.value) and "population" in str(caught.value)
    assert "govSections" not in str(caught.value) and "gus-wiek" not in str(caught.value)
    assert caught.value.detail is not None and "gus-wiek" in caught.value.detail
    assert Dataset.POPULATION not in other.tables and Dataset.UNEMPLOYMENT in other.tables
    assert service.calls.call_count == 1  # the page was valid: the cache kept it


def test_a_chart_whose_series_changed_is_unreadable_but_the_others_are_not(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """A renamed key of the area's values leaves a chart without a series: unreadable,
    while the unemployment reads as before."""
    spec = spec_of(WARSZAWA, "gus-powierzchnia-wykres")
    points = [
        {"period": p["period"], "values": {"sredniaM2": p["values"]["powierzchnia"]}}
        for p in spec["datasets"][""]["points"]
    ]
    edited = with_points(WARSZAWA, "gus-powierzchnia-wykres", "", points)

    serve(service, "warszawa", edited)
    adapter = GovernmentStatisticsApi(http)
    with pytest.raises(UnexpectedResponseError, match="niespójne") as caught:
        adapter.location_statistics(LocationSlug("warszawa"), Dataset.AVERAGE_AREA)
    other = adapter.location_statistics(LocationSlug("warszawa"), Dataset.UNEMPLOYMENT)

    assert caught.value.detail is not None and "gus-powierzchnia-wykres" in caught.value.detail
    assert Dataset.AVERAGE_AREA not in other.tables and Dataset.UNEMPLOYMENT in other.tables


def test_a_chart_the_page_no_longer_has_is_unreadable_while_its_section_is_listed(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """A renamed chart: the section ``gus-wynagrodzenia`` stays, its data is not found."""
    edited = WARSZAWA.replace(f'"id":"{WAGES_CHART}"'.encode(), b'"id":"wynagrodzenia-v3"', 1)

    with pytest.raises(UnexpectedResponseError, match="nieczytelne") as caught:
        published(http, service, "warszawa", edited, Dataset.WAGES)

    assert caught.value.detail is not None and "gus-wynagrodzenia" in caught.value.detail


@pytest.mark.parametrize(
    ("key", "match"),
    [("ruch|mies", "kontrakt"), ("przyrost|mies", "kontrakt")],
)
def test_a_chart_without_a_dataset_it_is_read_by_is_off_the_contract(
    http: HttpClient, service: respx.MockRouter, key: str, match: str
) -> None:
    spec = spec_of(POLSKA, "eurostat-demografia-wykres")
    datasets = {k: v for k, v in spec["datasets"].items() if k != key}
    edited = replace_prop(POLSKA, "spec", chart(spec["id"]), {**spec, "datasets": datasets})

    with pytest.raises(UnexpectedResponseError, match=match) as caught:
        published(http, service, "polska", edited, Dataset.DEMOGRAPHY)

    assert caught.value.detail is not None and key in caught.value.detail


def test_a_dataset_of_a_chart_the_client_does_not_read_does_not_matter(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """The sums of 12 months (``krocz``) of the demography of ``polska`` are not read."""
    edited = with_points(POLSKA, "eurostat-demografia-wykres", "ruch|krocz", [{"x": 1}])

    table = published(http, service, "polska", edited, Dataset.DEMOGRAPHY).tables[
        Dataset.DEMOGRAPHY
    ]

    assert values(table, "births")["2025-09"] == 22500


def test_a_period_twice_in_a_chart_is_inconsistent_data(
    http: HttpClient, service: respx.MockRouter
) -> None:
    points = spec_of(WARSZAWA, "gus-powierzchnia-wykres")["datasets"][""]["points"]
    edited = with_points(WARSZAWA, "gus-powierzchnia-wykres", "", [*points, points[-1]])

    with pytest.raises(UnexpectedResponseError, match="niespójne"):
        published(http, service, "warszawa", edited)


def test_points_of_two_datasets_of_a_chart_are_joined_by_period(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """The natural increase without its last year: that year has births and deaths and no
    increase, not a shifted series."""
    spec = spec_of(WARSZAWA, "gus-demografia-wykres")
    shorter = spec["datasets"]["przyrost"]["points"][:-1]
    edited = with_points(WARSZAWA, "gus-demografia-wykres", "przyrost", shorter)

    table = published(http, service, "warszawa", edited, Dataset.DEMOGRAPHY).tables[
        Dataset.DEMOGRAPHY
    ]

    assert table.periods[-1] == "2025"
    assert values(table, "natural_increase")["2025"] is None
    assert values(table, "natural_increase")["2024"] is not None
    assert values(table, "births")["2025"] == 14439


def test_every_row_must_have_the_keys_of_its_dataset(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """Rows are recognized by all of them, not by the first: one row without them makes
    that dataset unreadable, and only that one."""
    rows = rows_of(WARSZAWA, "data", "pierwotnyOfertowa")
    broken = [*rows[:-1], {"quarter": rows[-1]["quarter"], "pierwotny": 1}]
    edited = replace_prop(WARSZAWA, "data", rows_with("pierwotnyOfertowa"), broken)

    serve(service, "warszawa", edited)
    adapter = GovernmentStatisticsApi(http)
    with pytest.raises(UnexpectedResponseError, match="nieczytelne"):
        adapter.location_statistics(LocationSlug("warszawa"), Dataset.NBP_PRICES)
    other = adapter.location_statistics(LocationSlug("warszawa"), Dataset.UNEMPLOYMENT)

    assert Dataset.UNEMPLOYMENT in other.tables


def test_two_props_with_rows_of_one_dataset_are_ambiguous(
    http: HttpClient, service: respx.MockRouter
) -> None:
    nbp = rows_of(WARSZAWA, "data", "pierwotnyOfertowa")
    doubled = replace_prop(WARSZAWA, "data", rows_with("totalKobiety"), nbp[:-1])

    with pytest.raises(UnexpectedResponseError, match="niejednoznaczne") as caught:
        published(http, service, "warszawa", doubled)

    assert caught.value.detail is not None and "nbp_quarterly" in caught.value.detail


def test_the_same_rows_twice_are_no_ambiguity(http: HttpClient, service: respx.MockRouter) -> None:
    """The section ``gus-prs`` of ``polska`` gets ``monthlyData`` as a reference [P
    2026-10-31]; the same rows written out again in its place change nothing."""
    element = b'["$","$L3a",null,{"monthlyData":'  # the element of the section gus-prs
    reference = element + b'"$1e:1:props:blocks:gus:props:children:0:props:monthlyData"'
    rows = json.dumps(rows_of(POLSKA, "monthlyData", "month"), separators=(",", ":"))
    assert POLSKA.count(reference) == 1
    inlined = POLSKA.replace(reference, element + rows.encode())
    assert inlined.count(b'"monthlyData":[') == 2

    table = published(http, service, "polska", inlined, Dataset.DWELLINGS_MONTHLY).tables[
        Dataset.DWELLINGS_MONTHLY
    ]

    assert len(table.periods) == 260


def test_two_charts_of_one_dataset_are_ambiguous(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """The monthly wages of ``polska`` in place of the yearly ones of ``warszawa``, which
    also stay: which one is the city's?"""
    monthly = spec_of(POLSKA, "gus-wynagrodzenia-wykres")
    doubled = replace_prop(WARSZAWA, "spec", chart("gus-bezrobocie-wykres"), monthly)

    with pytest.raises(UnexpectedResponseError, match="niejednoznaczne") as caught:
        published(http, service, "warszawa", doubled)

    assert caught.value.detail is not None and "gus-wynagrodzenia-wykres" in caught.value.detail


def test_two_charts_with_one_id_are_ambiguous(http: HttpClient, service: respx.MockRouter) -> None:
    """The chart of the forms (not read) replaced by another area chart: two different
    charts ``gus-powierzchnia-wykres``."""
    area = spec_of(WARSZAWA, "gus-powierzchnia-wykres")
    points = area["datasets"][""]["points"]
    other = {**area, "datasets": {"": {**area["datasets"][""], "points": points[:-1]}}}
    doubled = replace_prop(WARSZAWA, "spec", chart("gus-formy-wykres"), other)

    with pytest.raises(UnexpectedResponseError, match="niejednoznaczne") as caught:
        published(http, service, "warszawa", doubled)

    assert caught.value.detail is not None and "dwa wykresy" in caught.value.detail


@pytest.mark.parametrize(
    ("added", "match"),
    [
        (b',"citySlug":"krakow"', "innej lokalizacji"),
        (b',"cityName":"Krak\xc3\xb3w"', "niejednoznaczne"),
        (b',"blocks":{"govSections":["nbp"]}', "niejednoznaczne"),
    ],
)
def test_a_second_location_name_or_list_of_sections_is_no_page_of_this_location(
    http: HttpClient, service: respx.MockRouter, added: bytes, match: str
) -> None:
    """Conflicting values of the props of the page's identity: another ``citySlug`` is
    another location's page, another ``cityName`` or ``govSections`` an ambiguous page (as
    ``RscPage.props`` treats conflicting values); the same value again is none of that."""
    edited = WARSZAWA.replace(b'"anchorId":"gus-wiek"', b'"anchorId":"gus-wiek"' + added, 1)
    assert edited != WARSZAWA

    with pytest.raises(UnexpectedResponseError, match=match):
        published(http, service, "warszawa", edited)


@pytest.mark.parametrize(
    "added",
    [
        b',"citySlug":"warszawa"',
        b',"cityName":"Warszawa"',
        b',"blocks":{"govSections":' + json.dumps(GOV_SECTIONS_OF_WARSZAWA).encode() + b"}",
    ],
)
def test_the_same_location_name_or_list_of_sections_again_is_no_conflict(
    http: HttpClient, service: respx.MockRouter, added: bytes
) -> None:
    edited = WARSZAWA.replace(b'"anchorId":"gus-wiek"', b'"anchorId":"gus-wiek"' + added, 1)

    page = published(http, service, "warszawa", edited)

    assert page.name == "Warszawa" and set(page.tables) == set(Dataset)


def test_rows_that_fit_two_datasets_are_ambiguous(
    http: HttpClient, service: respx.MockRouter
) -> None:
    rows = rows_of(WARSZAWA, "data", "totalKobiety")
    both = [dict(r, quarter="2025-Q1", oddane=1, rozpoczete=1, month="2025-01") for r in rows]
    edited = replace_prop(WARSZAWA, "data", rows_with("totalKobiety"), both)

    with pytest.raises(UnexpectedResponseError, match="niejednoznaczne") as caught:
        published(http, service, "warszawa", edited)

    assert caught.value.detail is not None and "pasuje do" in caught.value.detail


def test_a_period_twice_in_rows_is_inconsistent_data(
    http: HttpClient, service: respx.MockRouter
) -> None:
    rows = rows_of(WARSZAWA, "data", "pierwotnyOfertowa")
    edited = replace_prop(WARSZAWA, "data", rows_with("pierwotnyOfertowa"), [*rows, rows[-1]])

    with pytest.raises(UnexpectedResponseError, match="niespójne"):
        published(http, service, "warszawa", edited, Dataset.NBP_PRICES)


def test_rows_out_of_order_are_sorted(http: HttpClient, service: respx.MockRouter) -> None:
    rows = rows_of(WARSZAWA, "data", "totalKobiety")
    edited = replace_prop(WARSZAWA, "data", rows_with("totalKobiety"), rows[::-1])

    table = published(http, service, "warszawa", edited).tables[Dataset.POPULATION]

    assert table.periods == tuple(str(year) for year in range(2005, 2026))


def test_a_form_missing_from_the_dwellings_breaks_nothing(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """(a) A key outside the shape gone from every dwellings row (a city that does not
    list one form): unemployment reads as before, and the dwellings themselves only lose
    that series."""
    edited = dwellings_without(POLSKA, "oddaneZakladowe")
    assert b'"oddaneZakladowe"' in edited  # still in the chart of the forms

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
    rows = rows_of(POLSKA, "data", "quarter")
    edited = replace_prop(POLSKA, "data", lambda v: v == rows, [dict(rows[0], **broken)])

    page = published(http, service, "polska", edited, Dataset.UNEMPLOYMENT)

    assert Dataset.UNEMPLOYMENT in page.tables
    assert Dataset.DWELLINGS_QUARTERLY not in page.tables


def test_an_inconsistent_table_of_another_dataset_breaks_nothing(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """(b) A period twice in the unemployment: the area reads as before. Kills the mutant
    that re-raises for every dataset."""
    points = spec_of(POLSKA, "gus-bezrobocie-wykres")["datasets"][""]["points"]
    edited = with_points(POLSKA, "gus-bezrobocie-wykres", "", [*points, points[-1]])

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
    points = spec_of(POLSKA, "gus-bezrobocie-wykres")["datasets"][""]["points"]
    broken = [*points, points[-1]] if edit == "twice" else [dict(points[0], values="dużo")]
    edited = with_points(POLSKA, "gus-bezrobocie-wykres", "", broken)

    with pytest.raises(UnexpectedResponseError, match=match) as caught:
        published(http, service, "polska", edited, Dataset.UNEMPLOYMENT)

    assert SERVICE_CHANGED in str(caught.value)
    assert caught.value.detail is not None and "gus-bezrobocie-wykres" in caught.value.detail


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
    edited = replace_prop(POLSKA, prop, dwellings_rows(period), [])

    page = published(http, service, "polska", edited, asked)

    assert asked not in page.tables and kept in page.tables
    with pytest.raises(NotFoundError, match=f"^Serwis nie publikuje zestawu '{asked.value}'"):
        page.statistics(asked, PeriodCount())


def test_dwellings_listed_without_any_of_their_data_are_unreadable(
    http: HttpClient, service: respx.MockRouter
) -> None:
    edited = replace_prop(POLSKA, "data", dwellings_rows("quarter"), [])
    edited = replace_prop(edited, "monthlyData", dwellings_rows("month"), [])

    with pytest.raises(UnexpectedResponseError, match="nieczytelne"):
        published(http, service, "polska", edited, Dataset.DWELLINGS_MONTHLY)


def test_population_without_one_half_has_no_total(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """The total is women plus men, or nothing: a year without the men has no total
    (never the women alone), and the women stay."""
    rows = rows_of(POLSKA, "data", "totalKobiety")
    last = dict(rows[-1], totalMezczyzni=None)
    edited = replace_prop(POLSKA, "data", rows_with("totalKobiety"), [*rows[:-1], last])

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
        ({"year": 2025, "totalKobiety": "61", "totalMezczyzni": 5}, None),  # text numbers
        ({"year": "2025", "totalKobiety": 61, "totalMezczyzni": 5}, None),
        ({"year": 1850, "totalKobiety": 61, "totalMezczyzni": 5}, "year"),
        ({"year": True, "totalKobiety": 61, "totalMezczyzni": 5}, "year"),
        ({"year": 2025, "totalKobiety": "dużo", "totalMezczyzni": 5}, "totalKobiety"),
    ],
)
def test_values_are_checked_and_tolerated_like_the_rest_of_the_client(
    http: HttpClient, service: respx.MockRouter, row: dict[str, Any], problem: str | None
) -> None:
    edited = replace_prop(WARSZAWA, "data", rows_with("totalKobiety"), [row])

    if problem is None:
        table = published(http, service, "warszawa", edited).tables[Dataset.POPULATION]
        assert values(table, "total") == {"2025": 66.0}
        return
    with pytest.raises(UnexpectedResponseError, match="kontrakt") as caught:
        published(http, service, "warszawa", edited, Dataset.POPULATION)
    assert caught.value.detail is not None and problem in caught.value.detail


@pytest.mark.parametrize(
    ("key", "label"),
    [("quarter", "2025-Q5"), ("quarter", "2025Q1"), ("month", "2025-13"), ("month", "25-01")],
)
def test_period_labels_of_rows_are_checked(
    http: HttpClient, service: respx.MockRouter, key: str, label: str
) -> None:
    prop = "monthlyData" if key == "month" else "data"
    dataset = Dataset.DWELLINGS_MONTHLY if key == "month" else Dataset.DWELLINGS_QUARTERLY
    rows = rows_of(WARSZAWA, prop, key)
    edited = replace_prop(WARSZAWA, prop, dwellings_rows(key), [dict(rows[0], **{key: label})])

    with pytest.raises(UnexpectedResponseError, match="kontrakt"):
        published(http, service, "warszawa", edited, dataset)
    other = GovernmentStatisticsApi(http).location_statistics(
        LocationSlug("warszawa"), Dataset.AVERAGE_AREA
    )
    assert dataset not in other.tables and Dataset.AVERAGE_AREA in other.tables


@pytest.mark.parametrize("label", ["2025-01", "25", "2025-Q1", ""])
def test_period_labels_of_charts_are_checked_against_their_frequency(
    http: HttpClient, service: respx.MockRouter, label: str
) -> None:
    """A yearly chart with another label: inconsistent, and only that dataset."""
    points = spec_of(WARSZAWA, "gus-powierzchnia-wykres")["datasets"][""]["points"]
    edited = with_points(WARSZAWA, "gus-powierzchnia-wykres", "", [dict(points[0], period=label)])

    with pytest.raises(UnexpectedResponseError, match="niespójne"):
        published(http, service, "warszawa", edited)
    other = GovernmentStatisticsApi(http).location_statistics(
        LocationSlug("warszawa"), Dataset.UNEMPLOYMENT
    )
    assert Dataset.UNEMPLOYMENT in other.tables


# --- what the page is about -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("served", "asked"),
    [("warszawa", "krakow"), ("polska", "krakow"), ("warszawa", "polska"), ("7-miast", "10-miast")],
)
def test_the_page_of_another_location_is_unexpected(
    http: HttpClient, service: respx.MockRouter, served: str, asked: str
) -> None:
    """A page for another location (e.g. the root page served for an unknown city, [H]) is
    never returned as the asked one's: its ``citySlug`` must be the location (none for
    ``polska`` [P 2026-10-31])."""
    serve(service, asked, raw(STATS_PAGES[served]))

    with pytest.raises(UnexpectedResponseError, match="innej lokalizacji") as caught:
        GovernmentStatisticsApi(http).statistics_page(LocationSlug(asked))

    assert caught.value.detail is not None and "citySlug" in caught.value.detail


def test_a_page_without_its_location_is_unexpected(
    http: HttpClient, service: respx.MockRouter
) -> None:
    edited = WARSZAWA.replace(b'"citySlug":"warszawa"', b'"slug":"warszawa"')
    assert b'"citySlug"' not in edited

    with pytest.raises(UnexpectedResponseError, match="innej lokalizacji"):
        published(http, service, "warszawa", edited)


def test_the_page_of_polska_may_name_itself(http: HttpClient, service: respx.MockRouter) -> None:
    """A ``citySlug`` of ``polska`` on its own page is no other location."""
    named = WARSZAWA.replace(b'"citySlug":"warszawa"', b'"citySlug":"polska"')
    serve(service, "polska", named)

    page = GovernmentStatisticsApi(http).statistics_page(LocationSlug("polska"))

    assert page.cityName == "Warszawa" and len(page.govSections) == 8


def test_a_city_without_its_name_is_named_by_its_slug(
    http: HttpClient, service: respx.MockRouter
) -> None:
    edited = WARSZAWA.replace(b'"cityName":"Warszawa"', b'"name":"Warszawa"')

    assert published(http, service, "warszawa", edited).name == "warszawa"


# --- answers that are no page of statistics --------------------------------------------------


@pytest.mark.parametrize("location", ["nieistniejace-miasto", "jastrzebie"])
def test_an_unknown_location_is_not_found(
    http: HttpClient, service: respx.MockRouter, location: str
) -> None:
    """[P 2026-10-31] a 404 whose body is a flight stream (``text/x-component``): the
    page's own answer to a location it does not know. ``jastrzebie`` is the 1.0 slug of
    Jastrzębie-Zdrój, which no 2.0 page links."""
    service.get(path=stats_path(location)).respond(404, **unknown_location_page())

    with pytest.raises(NotFoundError) as caught:
        GovernmentStatisticsApi(http).statistics_page(LocationSlug(location))

    assert caught.value.detail is not None
    assert f"/statystyki/{location}/dane-rzadowe" in caught.value.detail
    assert "text/x-component" in caught.value.detail


@pytest.mark.parametrize("answer", ["404 flight", "200 marker"])
@pytest.mark.parametrize(
    "location",
    [
        "polska",
        "7-miast",
        "10-miast",
        "6-miast-bez-warszawy",
        "warszawa",
        "sopot",
        "jastrzebie-zdroj",
    ],
)
def test_the_known_locations_are_never_unknown(
    http: HttpClient, service: respx.MockRouter, location: str, answer: str
) -> None:
    """Every location the pages link has its page: "unknown" for one of them (a 404 flight
    stream, or Next.js's marker in a 200) is a change of the service (D21), e.g. a renamed
    section of the one catch-all route, never "give a valid location" to a model that gave
    one."""
    route = service.get(path=stats_path(location))
    if answer == "404 flight":
        route.respond(404, **unknown_location_page())
    else:
        route.respond(200, content=raw(OFFERS_UNKNOWN_CITY_20261031), headers=RSC)

    with pytest.raises(UnexpectedResponseError) as caught:
        GovernmentStatisticsApi(http).location_statistics(
            LocationSlug(location), Dataset.AVERAGE_AREA
        )

    assert str(caught.value) == CHANGED_SERVICE
    assert caught.value.detail is not None and f"{location}/dane-rzadowe" in caught.value.detail


def test_the_known_locations_are_the_ones_every_page_links() -> None:
    """[P 2026-10-31] „Dostępne lokalizacje danych rządowych”: each page links the other
    locations but ``polska`` (the root), the page of ``polska`` all 69 (3 aggregates first,
    then 66 cities, Jastrzębie-Zdrój as ``jastrzebie-zdroj``): the same 70 on all three."""
    found = {}
    for location, page in STATS_PAGES.items():
        links = [
            slug.decode()
            for slug in re.findall(
                rb'"href":"/statystyki/([a-z0-9-]+)/dane-rzadowe#dane-gus"', raw(page)
            )
        ]
        assert len(links) == len(set(links)) and location not in links
        assert "polska" not in links
        found[location] = {"polska", location, *links}

    assert all(links == KNOWN_LOCATIONS for links in found.values())
    assert len(KNOWN_LOCATIONS) == 70
    assert {"7-miast", "10-miast", "6-miast-bez-warszawy", "jastrzebie-zdroj"} <= KNOWN_LOCATIONS
    assert "jastrzebie" not in KNOWN_LOCATIONS


def test_a_removed_page_is_a_changed_service_not_an_unknown_location(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """D21: the HTML not-found page of a removed route, also for an unknown city."""
    service.get(path=stats_path("krakow")).respond(404, **removed_route())

    with pytest.raises(UnexpectedResponseError) as caught:
        GovernmentStatisticsApi(http).statistics_page(LocationSlug("krakow"))

    assert str(caught.value) == CHANGED_SERVICE


def test_the_old_route_redirecting_is_a_changed_service(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """The page itself answering 308 (as the 1.0 route does) is never followed."""
    target = f"{BASE}/statystyki/krakow/dane-rzadowe-v3"
    service.get(path=stats_path("krakow")).respond(308, headers={"Location": target})

    with pytest.raises(UnexpectedResponseError) as caught:
        GovernmentStatisticsApi(http).statistics_page(LocationSlug("krakow"))

    assert str(caught.value) == CHANGED_SERVICE
    assert service.calls.call_count == 1


def test_a_page_with_nextjs_404_marker_is_not_found(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """Next.js's marker in a 200, as the 2.0 offer lists answer an unknown city
    [P 2026-10-31]; the statistics pages answer a 404 instead [P 2026-10-31]."""
    serve(service, "nieistniejace-miasto", raw(OFFERS_UNKNOWN_CITY_20261031))

    with pytest.raises(NotFoundError) as caught:
        GovernmentStatisticsApi(http).statistics_page(LocationSlug("nieistniejace-miasto"))

    assert caught.value.detail == (
        "/statystyki/nieistniejace-miasto/dane-rzadowe: brak propsa 'blocks.govSections', "
        "strona zgłasza NEXT_HTTP_ERROR_FALLBACK;404"
    )


def test_a_page_without_data_nor_404_marker_is_unexpected(
    http: HttpClient, service: respx.MockRouter
) -> None:
    payload = raw(OFFERS_UNKNOWN_CITY_20261031).replace(b"NEXT_HTTP_ERROR_FALLBACK;404", b"x")
    serve(service, "nieistniejace-miasto", payload)

    with pytest.raises(UnexpectedResponseError) as caught:
        GovernmentStatisticsApi(http).statistics_page(LocationSlug("nieistniejace-miasto"))

    assert SERVICE_CHANGED in str(caught.value)
    assert caught.value.detail is not None and "govSections" in caught.value.detail


def test_the_page_served_as_html_is_read_from_its_scripts(
    http: HttpClient, service: respx.MockRouter
) -> None:
    push = json.dumps(WARSZAWA.decode(), ensure_ascii=False)
    html = f"<!DOCTYPE html><html><script>self.__next_f.push([1,{push}])</script></html>"
    service.get(path=stats_path("warszawa")).respond(
        200, content=html.encode(), headers={"Content-Type": "text/html; charset=utf-8"}
    )

    page = GovernmentStatisticsApi(http).location_statistics(
        LocationSlug("warszawa"), Dataset.NBP_PRICES
    )

    assert values(page.tables[Dataset.NBP_PRICES], "primary_transaction")["2026-Q2"] == 16783
