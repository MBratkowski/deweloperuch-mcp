"""Contract of ``deweloperuch_mcp.api.dto.government_stats_page_dto`` with the service's
real answers: the 2.0 pages of 2026-10-31 (tests/fixtures/rsc/stats_gov_*_20261031.rsc) and
the sample of their sections (docs/discovery/samples/page.stats_gov.v2_sections.json).
"""

from typing import Any

import pytest
from pydantic import ValidationError

from deweloperuch_mcp.api.dto import government_stats_page_dto as page_dto
from deweloperuch_mcp.api.dto.dto import Dto
from deweloperuch_mcp.api.dto.government_stats_page_dto import (
    CHARTS,
    CHARTS_WITHOUT_SERIES,
    ROWS,
    SECTIONS,
    STATS_SHAPES,
    ChartDataDto,
    ChartSpecDto,
    GovernmentStatsPageDto,
)
from deweloperuch_mcp.flight import component_props, error_digests
from deweloperuch_mcp.models.government_statistics import Dataset
from deweloperuch_mcp.models.values import LocationSlug
from support.providers.routes.government_statistics import STATS_PAGES
from support.providers.rsc import raw
from support.providers.samples import body, envelope

GOV_SECTIONS = {
    "warszawa": [
        "gus-mieszkania",
        "gus-formy-budownictwa",
        "gus-srednia-powierzchnia",
        "gus-demografia",
        "gus-wiek",
        "gus-bezrobocie",
        "gus-wynagrodzenia",
        "nbp",
    ],
    "polska": [
        "gus-mieszkania",
        "gus-formy-budownictwa",
        "gus-srednia-powierzchnia",
        "gus-prs",
        "eurostat-demografia",
        "gus-wiek",
        "gus-bezrobocie",
        "gus-wynagrodzenia",
        "nbp-grid",
    ],
    "7-miast": [
        "gus-mieszkania",
        "gus-formy-budownictwa",
        "gus-srednia-powierzchnia",
        "gus-prs",
        "gus-demografia",
        "gus-wiek",
        "gus-bezrobocie",
        "nbp",
    ],
}
"""``blocks.govSections`` of each page [P 2026-10-31] (tests/fixtures/rsc/README.md)."""

ROW_FIELDS = {
    "warszawa": {"dwellings_quarterly", "dwellings_monthly", "population_yearly", "nbp_quarterly"},
    "polska": {"dwellings_quarterly", "dwellings_monthly", "population_yearly"},
    "7-miast": {"dwellings_quarterly", "dwellings_monthly", "population_yearly", "nbp_quarterly"},
}
"""The data props each page has, by the DTO's fields: ``polska`` has no NBP rows."""

CHART_IDS = {
    "warszawa": {
        "gus-powierzchnia-wykres",
        "gus-demografia-wykres",
        "gus-bezrobocie-wykres",
        "gus-wynagrodzenia-roczne-wykres",
    },
    "polska": {
        "gus-powierzchnia-wykres",
        "eurostat-demografia-wykres",
        "gus-bezrobocie-wykres",
        "gus-wynagrodzenia-wykres",
    },
    "7-miast": {"gus-powierzchnia-wykres", "gus-demografia-wykres", "gus-bezrobocie-miasta-wykres"},
}
"""The charts of each page the client knows (``CHARTS``, ``CHARTS_WITHOUT_SERIES``); the
pages also have ``gus-formy-wykres`` (dwellings by form, the rows of ``monthlyData``)."""


def props_of(location: str) -> list[tuple[str, Any]]:
    return list(component_props(raw(STATS_PAGES[location])))


def page_of(location: str) -> GovernmentStatsPageDto:
    return GovernmentStatsPageDto.from_payload(
        raw(STATS_PAGES[location]), path="/x", location=LocationSlug(location)
    )


def charts_of(location: str) -> dict[str, dict[str, Any]]:
    return {v["id"]: v for n, v in props_of(location) if n == "spec" and isinstance(v, dict)}


@pytest.mark.parametrize("location", list(STATS_PAGES))
def test_the_fixtures_are_pages_without_a_404_marker(location: str) -> None:
    payload = raw(STATS_PAGES[location])

    assert error_digests(payload) == []
    assert b"deweloperuch@" not in payload  # the contact address is redacted
    names = [name for name, value in component_props(payload) if isinstance(value, list)]
    assert "tocItems" not in names and "sortedLocations" not in names  # gone on 2.0


@pytest.mark.parametrize("location", list(STATS_PAGES))
def test_each_page_lists_its_own_sections(location: str) -> None:
    """``blocks.govSections`` differ per location [P 2026-10-31]."""
    blocks = [v for n, v in props_of(location) if n == "blocks"]

    assert len(blocks) == 1
    assert blocks[0]["govSections"] == GOV_SECTIONS[location]
    assert page_of(location).govSections == GOV_SECTIONS[location]


def test_the_sample_of_the_sections_is_the_page_of_warszawa() -> None:
    """docs/discovery/samples/page.stats_gov.v2_sections.json keeps 3 of the 8 ids (the
    sample convention); they are the first ones of the fixture of the same day."""
    sample = envelope("page.stats_gov.v2_sections")

    assert sample["_request"] == "GET /statystyki/warszawa/dane-rzadowe (RSC)"
    assert sample["_prop"] == "govSections"
    kept = body("page.stats_gov.v2_sections")
    assert kept == GOV_SECTIONS["warszawa"][: len(kept)] and len(kept) == 3


@pytest.mark.parametrize("location", list(STATS_PAGES))
def test_the_data_props_are_recognized_by_their_rows(location: str) -> None:
    """[P 2026-10-31] three or four props of rows: ``data`` ×3 (×2 on ``polska``) and
    ``monthlyData``, each matching one shape; the NBP grid of ``polska`` matches none."""
    page = page_of(location)

    found = {field for field in page_dto.STATS_ROWS if getattr(page, field) is not None}
    assert found == ROW_FIELDS[location]
    sizes = {field: len(getattr(page, field)) for field in found}
    assert sizes == {
        "dwellings_quarterly": 87,
        "dwellings_monthly": 260,
        "population_yearly": 21,
        **({"nbp_quarterly": 80} if "nbp_quarterly" in found else {}),
    }


@pytest.mark.parametrize("location", list(STATS_PAGES))
def test_the_known_charts_of_each_page(location: str) -> None:
    assert set(page_of(location).charts) == CHART_IDS[location]
    assert set(charts_of(location)) == CHART_IDS[location] | {"gus-formy-wykres"}


@pytest.mark.parametrize(
    ("location", "chart"),
    [
        (location, chart)
        for location in STATS_PAGES
        for chart in CHARTS
        if chart.chart_id in CHART_IDS[location]
    ],
)
def test_every_chart_read_has_the_datasets_it_is_read_by(location: str, chart: Any) -> None:
    """The contract of each chart, on every page that has it: the datasets ``CHARTS`` reads
    are there, and every point has the value each series is read from [P 2026-10-31]."""
    parsed = Dto.validated(ChartSpecDto, charts_of(location)[chart.chart_id], chart.chart_id)

    for _, key, values_key in chart.columns:
        data = Dto.validated(ChartDataDto, parsed.datasets[key], key)
        assert data.points
        if values_key is not None:
            assert all(values_key in point.values for point in data.points), values_key


def test_the_series_keys_of_the_charts() -> None:
    """The keys of the values each chart is read by, as the pages give them."""
    expected = {
        ("warszawa", "gus-powierzchnia-wykres", ""): {"powierzchnia"},
        ("warszawa", "gus-demografia-wykres", "ruch"): {"urodzenia", "zgony"},
        ("warszawa", "gus-demografia-wykres", "przyrost"): {"przyrost"},
        ("warszawa", "gus-bezrobocie-wykres", ""): {"miejsce", "polska"},
        ("warszawa", "gus-wynagrodzenia-roczne-wykres", ""): {"brutto"},
        ("polska", "eurostat-demografia-wykres", "ruch|mies"): {"urodzenia", "zgony"},
        ("polska", "eurostat-demografia-wykres", "przyrost|mies"): {"przyrost"},
        ("polska", "gus-bezrobocie-wykres", ""): {"miejsce", "polska"},
        ("polska", "gus-wynagrodzenia-wykres", ""): {"brutto"},
        ("7-miast", "gus-demografia-wykres", "ruch"): {"urodzenia", "zgony"},
    }

    for (location, chart_id, key), keys in expected.items():
        points = charts_of(location)[chart_id]["datasets"][key]["points"]
        assert {k for point in points for k in point["values"]} == keys, (location, chart_id)


def test_the_unemployment_of_an_aggregate_is_one_series_per_city() -> None:
    """[P 2026-10-31] ``7-miast``: the chart of its section ``gus-bezrobocie`` has one rate
    per city of the aggregate, keyed by the cities' slugs, and no rate of its own."""
    chart = charts_of("7-miast")["gus-bezrobocie-miasta-wykres"]

    series = [item["key"] for item in chart["datasets"][""]["series"]]
    assert sorted(series) == ["gdansk", "gdynia", "krakow", "lodz", "poznan", "warszawa", "wroclaw"]
    assert CHARTS_WITHOUT_SERIES == {"gus-bezrobocie-miasta-wykres": Dataset.UNEMPLOYMENT}


def test_the_notes_of_the_yearly_wages_are_the_ratio_to_the_national_average() -> None:
    """[P 2026-10-31] ``warszawa``: one note per year, the ratio to the national average,
    as the section's own text says."""
    points = charts_of("warszawa")["gus-wynagrodzenia-roczne-wykres"]["datasets"][""]["points"]
    info = [v for n, v in props_of("warszawa") if n == "info" and isinstance(v, list)]

    assert [point["notes"] for point in points[:2]] == [
        ["144,1\xa0% średniej krajowej"],
        ["143,7\xa0% średniej krajowej"],
    ]
    assert all(len(point["notes"]) == 1 for point in points)
    assert any("relacja do średniej krajowej (Polska = 100 %)" in str(item) for item in info)


@pytest.mark.parametrize("location", ["warszawa", "7-miast"])
def test_the_page_names_its_location(location: str) -> None:
    city = {n: v for n, v in props_of(location) if n in ("citySlug", "cityName")}

    assert city == {
        "citySlug": location,
        "cityName": {"warszawa": "Warszawa", "7-miast": "Top 7 miast Polski"}[location],
    }


def test_the_page_of_the_whole_country_has_no_city() -> None:
    names = {n for n, _ in props_of("polska")}

    assert "citySlug" not in names and "cityName" not in names


@pytest.mark.parametrize("location", list(STATS_PAGES))
def test_every_section_a_table_links_to_is_listed_by_its_page(location: str) -> None:
    """The anchors come from the page's own sections: ``polska`` has no ``nbp`` and shows
    its demography as ``eurostat-demografia``; ``7-miast`` has no wages section."""
    sections = set(GOV_SECTIONS[location])

    for dataset, ids in SECTIONS.items():
        listed = set(ids) & sections
        if (location, dataset) in {("polska", Dataset.NBP_PRICES), ("7-miast", Dataset.WAGES)}:
            assert not listed
            continue
        assert len(listed) == 1, (location, dataset)
    assert {"eurostat-demografia", "nbp-grid"} <= set(GOV_SECTIONS["polska"])


def test_the_page_dto_refuses_sections_that_are_not_ids() -> None:
    with pytest.raises(ValidationError):
        GovernmentStatsPageDto.model_validate({"govSections": [{"id": "nbp"}]})


def test_every_data_field_has_its_row() -> None:
    fields = set(GovernmentStatsPageDto.model_fields) - {"govSections", "cityName", "charts"}

    assert set(page_dto.STATS_ROWS) == fields


def test_every_shape_has_keys_no_other_shape_has_all_of() -> None:
    """No row of one dataset can fit another dataset's shape on its own keys."""
    for shape in STATS_SHAPES:
        for other in STATS_SHAPES:
            if other is not shape:
                assert not other.keys <= shape.keys, (shape.field, other.field)


def test_shapes_fields_readings_and_sections_agree() -> None:
    """Each recognized prop has a field in the page DTO and a reading of one dataset; the
    charts read the other datasets, and every dataset has its sections."""
    shapes = {shape.field for shape in STATS_SHAPES}
    rows = {reading.field: reading.dataset for reading in ROWS}

    assert shapes == set(rows) == set(page_dto.STATS_ROWS)
    assert set(rows.values()) | {chart.dataset for chart in CHARTS} == set(Dataset) == set(SECTIONS)
    assert not set(rows.values()) & {chart.dataset for chart in CHARTS}
    ids = [chart.chart_id for chart in CHARTS]
    assert len(set(ids)) == len(ids) and not set(ids) & set(CHARTS_WITHOUT_SERIES)
