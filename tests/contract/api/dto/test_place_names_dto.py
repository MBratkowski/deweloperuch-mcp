"""Contract of ``deweloperuch_mcp.api.dto.place_names_dto`` with the service's real
answers: the names of the 66 cities in the packaged table are the names the government
statistics pages give them (tests/fixtures/rsc/stats_gov_polska_20261031.rsc, the page
``get_government_statistics`` reads), so both tools name a city alike.
"""

import json
import re

from deweloperuch_mcp.api.dto.place_names_dto import PlaceNamesDto
from support.providers.rsc import STATS_GOV_POLSKA_20261031, raw

CITY_LINK = re.compile(
    rb'"href":"/statystyki/([a-z0-9-]+)/dane-rzadowe#dane-gus",'
    rb'"className":"[^"]*","children":("(?:[^"\\]|\\.)*")'
)
"""A link of „Dostępne lokalizacje danych rządowych” with its text [P 2026-10-31]."""

AGGREGATES = {"7-miast", "10-miast", "6-miast-bez-warszawy"}


def test_the_table_names_the_cities_as_the_government_page_does() -> None:
    """[P 2026-10-31] e.g. „Bielsko-Biała” and „Jastrzębie-Zdrój”, where the register's own
    place names are „Bielsko-biała” and „Jastrzębie-zdrój” (tests/fixtures/api/
    tx_cities_20261102.json)."""
    links = {
        slug.decode(): json.loads(text)
        for slug, text in CITY_LINK.findall(raw(STATS_GOV_POLSKA_20261031))
        if slug.decode() not in AGGREGATES
    }

    assert len(links) == 66
    assert dict(PlaceNamesDto.packaged().cities) == links
