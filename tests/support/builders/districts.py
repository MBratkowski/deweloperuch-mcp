"""Test data of a city's districts with offers: the real answer of the offers variant of
``city-districts`` for Warszawa (tests/fixtures/api/city_districts_warszawa_20261102.json,
18 districts in the service's order), as JSON and as the domain's ``District``, and the
texts of a search in a district the service does not list.
"""

import copy
import json
from typing import Any

from deweloperuch_mcp.models.district import District
from support.paths import API_FIXTURES

WARSZAWA_DISTRICTS_20261102 = API_FIXTURES / "city_districts_warszawa_20261102.json"
"""``GET /api/city-districts?citySlug=warszawa`` on 2026-11-02 (no ``variant``: the offers'
districts), byte-exact."""

WARSZAWA_NAMES = (
    "Białołęka, Praga-Północ, Mokotów, Targówek, Bemowo, Włochy, Praga-Południe, Ursus, "
    "Ursynów, Wola, Bielany, Ochota, Śródmieście, Rembertów, Wawer, Wilanów, Wesoła, Żoliborz"
)
"""The 18 names, in the service's order."""


def warszawa_districts_body() -> dict[str, Any]:
    """The answer as the service sent it (a new copy on every call)."""
    found: dict[str, Any] = json.loads(WARSZAWA_DISTRICTS_20261102.read_bytes())
    return found


def districts_of(found: dict[str, Any]) -> tuple[District, ...]:
    """The districts of an answer, in its order."""
    return tuple(District(name=row["name"], slug=row["slug"]) for row in found["districts"])


def warszawa_districts() -> tuple[District, ...]:
    """The 18 districts of the real answer, in its order."""
    return districts_of(warszawa_districts_body())


def with_service_slug(name: str, slug: str) -> dict[str, Any]:
    """The real answer with the district ``name`` given the slug ``slug``: a service that
    addresses a district by another slug than the client makes of its name. Every slug of
    the 18 equals the client's [P 2026-11-01], so no real answer has one; only that slug is
    changed."""
    found = copy.deepcopy(warszawa_districts_body())
    rows = [row for row in found["districts"] if row["name"] == name]
    assert len(rows) == 1, name
    rows[0]["slug"] = slug
    return found


def unlisted_district_message(district: str, city: str = "warszawa") -> str:
    """The refusal of a district the service does not list in Warszawa's answer: every one
    of its 18 districts fits."""
    return (
        f"Serwis nie zna dzielnicy {district!r} w mieście {city!r}. Znane dzielnice tego "
        f"miasta: {WARSZAWA_NAMES}. Podaj w district jedną z nich albo szukaj bez district."
    )


def no_districts_message(district: str, city: str) -> str:
    """The refusal of a district in a city for which the service lists none."""
    return (
        f"Serwis nie zna dzielnicy {district!r} w mieście {city!r} i nie podaje dla tego "
        "miasta żadnych dzielnic z ofertami. Szukaj bez district albo sprawdź city_slug w "
        "search_locations."
    )
