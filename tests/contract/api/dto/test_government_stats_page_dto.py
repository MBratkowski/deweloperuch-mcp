"""Contract of ``deweloperuch_mcp.api.dto.government_stats_page_dto`` with the service's
real answers (the samples in docs/discovery/samples/, the raw payloads in
tests/fixtures/).
"""

from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from deweloperuch_mcp.api.dto import government_stats_page_dto as page_dto
from deweloperuch_mcp.api.dto.dto import Dto
from deweloperuch_mcp.api.dto.government_stats_page_dto import MAPPINGS, SECTIONS
from deweloperuch_mcp.errors import UnexpectedResponseError
from deweloperuch_mcp.flight import component_props, error_digests
from deweloperuch_mcp.models.government_statistics import Dataset
from support.providers.rsc import (
    STATS_FIXTURES,
    STATS_POLSKA,
    STATS_WARSZAWA,
    raw,
)
from support.providers.samples import envelope, untrimmed


def stats_sample() -> dict[str, Any]:
    props: dict[str, Any] = untrimmed(envelope("page.stats_gov")["props"])
    return props


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


def test_the_sample_parses_with_the_page_dto() -> None:
    """docs/discovery/samples/page.stats_gov.json (warszawa, 2026-10-09): its `data` has
    the rows of quarterly dwellings, its `monthlyData` those of monthly ones."""
    props = stats_sample()

    parsed = page_dto.GovernmentStatsPageDto.model_validate(
        {
            "tocItems": props["tocItems"],
            "sortedLocations": props["sortedLocations"],
            "dwellings_quarterly": props["data"],
            "dwellings_monthly": props["monthlyData"],
        }
    )
    quarters = Dto.validated_rows(
        page_dto.DwellingsQuarterDto, parsed.dwellings_quarterly, "sample"
    )
    months = Dto.validated_rows(page_dto.DwellingsMonthDto, parsed.dwellings_monthly, "sample")

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
    shapes = {shape.field: shape for shape in page_dto.STATS_SHAPES}
    assert all(shapes["dwellings_quarterly"].keys <= set(row) for row in props["data"])
    assert all(shapes["dwellings_monthly"].keys <= set(row) for row in props["monthlyData"])


def test_the_page_dto_refuses_the_trimming_markers() -> None:
    props = envelope("page.stats_gov")["props"]

    with pytest.raises(ValidationError):
        page_dto.GovernmentStatsPageDto.model_validate(
            {"tocItems": props["tocItems"], "dwellings_quarterly": props["data"]}
        )
    with pytest.raises(UnexpectedResponseError, match="kontrakt"):
        Dto.validated_rows(page_dto.DwellingsQuarterDto, [*props["data"][:3], {"x": 1}], "sample")


def test_every_data_field_has_its_row() -> None:
    fields = set(page_dto.GovernmentStatsPageDto.model_fields) - {"tocItems", "sortedLocations"}

    assert set(page_dto.STATS_ROWS) == fields


def test_every_shape_has_keys_no_other_shape_of_another_group_has_all_of() -> None:
    """No row of one dataset can fit another dataset's shape on its own keys."""
    for shape in page_dto.STATS_SHAPES:
        for other in page_dto.STATS_SHAPES:
            if other.group != shape.group:
                assert not other.keys <= shape.keys, (shape.field, other.field)


def test_shapes_fields_and_mappings_agree() -> None:
    """Each recognized prop has a field in the page DTO and a mapping to one dataset; the
    shapes of one group map to the same dataset (one table per dataset and page)."""
    shapes = {shape.field: shape for shape in page_dto.STATS_SHAPES}
    fields = set(page_dto.GovernmentStatsPageDto.model_fields) - {"tocItems", "sortedLocations"}
    mappings = {mapping.field: mapping for mapping in MAPPINGS}

    assert set(shapes) == fields == set(mappings)
    for field, shape in shapes.items():
        same_group = [f for f, other in shapes.items() if other.group == shape.group]
        assert {mappings[f].dataset for f in same_group} == {mappings[field].dataset}
    assert {mapping.dataset for mapping in MAPPINGS} == set(Dataset) == set(SECTIONS)
