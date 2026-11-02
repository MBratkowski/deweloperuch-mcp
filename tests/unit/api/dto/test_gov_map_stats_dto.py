"""Tests of ``deweloperuch_mcp.api.dto.gov_map_stats_dto``."""

from deweloperuch_mcp.api.dto.gov_map_stats_dto import DATASETS, KEYS
from deweloperuch_mcp.api.dto.government_stats_page_dto import SECTIONS
from deweloperuch_mcp.models.indicator_ranking import Indicator
from support.providers.samples import body


def test_every_indicator_has_its_key_of_the_sample() -> None:
    """The seven keys of ``asOf`` and of each row's ``values`` [P 2026-11-01]."""
    sample = body("api.gov_map_stats")

    assert set(KEYS) == set(Indicator)
    assert set(KEYS.values()) == set(sample["asOf"]) == set(sample["rows"][0]["values"])


def test_every_indicator_has_a_section_of_a_citys_page() -> None:
    """The anchor of ``stats_url``: a section the page of a city lists (``gus-*``, ``nbp``);
    ``polska``'s own ids (``eurostat-demografia``) are never one."""
    assert set(DATASETS) == set(Indicator)
    assert {SECTIONS[dataset][0] for dataset in DATASETS.values()} == {
        "gus-bezrobocie",
        "gus-wynagrodzenia",
        "gus-mieszkania",
        "gus-srednia-powierzchnia",
        "gus-demografia",
        "nbp",
    }
