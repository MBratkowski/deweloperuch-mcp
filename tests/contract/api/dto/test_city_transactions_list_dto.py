"""Contract of ``deweloperuch_mcp.api.dto.city_transactions_list_dto`` with the service's
real answers (the samples in docs/discovery/samples/, the raw payloads in
tests/fixtures/).
"""

from support.providers.samples import body, envelope


def test_the_city_slugs_are_those_of_search_locations() -> None:
    """[W] for every place (the MCP description of city_slug): the samples name Kraków
    with the same slug in the ranking and in ``/api/cities`` [P 2026-10-09]."""
    ranked = {city["city"]: city["city_slug"] for city in body("api.city_tx_stats")}
    found = {city["city"]: city["city_slug"] for city in body("api.cities_q")["cityMappings"]}

    shared = ranked.keys() & found.keys()
    assert shared == {"Kraków"}
    assert all(ranked[name] == found[name] for name in shared)


def test_the_city_ranking_has_more_places_than_poland_has_towns() -> None:
    """[W] behind "także małe miasteczka i wsie" (level=city): the service ranks 2448
    places [P 2026-10-09]; Poland has about 1000 towns, so villages are among them."""
    assert envelope("api.city_tx_stats")["response"][-1] == "... (2445 more, 2448 total)"
