"""Tests of ``deweloperuch_mcp.consumers.cli.commands.locations_commands``."""

import json

import respx

from support.providers.cli import Cli, ok
from support.providers.routes.locations import location_routes


def test_locations_search_prints_locations_with_their_city_slugs(
    run: Cli, service: respx.MockRouter
) -> None:
    location_routes(service)

    out = ok(run("locations", "search", "krak"))

    assert out.splitlines()[0] == "Lokalizacje: 5."
    assert "miasto     Kraków [krakow] · ofert: 8 082" in out
    # [W] for districts and streets: "ok."
    assert "dzielnica  Mokotów, Warszawa [warszawa] · ofert: ok. 1 562" in out
    assert "ulica      Mokotów, Warszawa [warszawa] · ofert: ok. 191" in out
    assert "deweloperuch offers search CITY_SLUG" in out


def test_locations_search_json_is_the_domain_model(run: Cli, service: respx.MockRouter) -> None:
    location_routes(service)

    data = json.loads(ok(run("locations", "search", "krak", "--json")))

    assert (data["total"], data["returned"], data["truncated"], data["hint"]) == (5, 5, False, None)
    assert data["items"][0] == {
        "kind": "city",
        "name": "Kraków",
        "city": "Kraków",
        "city_slug": "krakow",
        "district": None,
        "street": None,
        "lat": None,
        "lng": None,
        "offer_count": 8082,
    }


def test_locations_search_without_matches_shows_the_hint(
    run: Cli, service: respx.MockRouter
) -> None:
    empty = {"cities": [], "cityMappings": [], "hasMore": False, "total": 0, "page": 1}
    service.get(path="/api/cities").respond(200, json=empty)
    service.get(path="/api/location-search").respond(200, json={"suggestions": []})

    out = ok(run("locations", "search", "xyzzy"))

    assert out.splitlines()[0] == "Lokalizacje: 0."
    assert "Wskazówka: Nic nie pasuje do 'xyzzy'." in out
