"""Tests of ``deweloperuch_mcp.models.location``."""

import pytest

from deweloperuch_mcp.models.location import Location, LocationMatches, LocationSearchResult
from deweloperuch_mcp.models.values import LocationQuery


def place(name: str) -> Location:
    return Location.city_of(name=name, city_slug=name.lower(), offer_count=1)


def test_locations_cities_first_with_a_total() -> None:
    result = LocationSearchResult.of(
        LocationQuery("krak"),
        LocationMatches((place("Kraków"),)),
        LocationMatches((place("Mokotów"),)),
    )

    assert [item.name for item in result.items] == ["Kraków", "Mokotów"]
    assert (result.total, result.returned, result.truncated, result.hint) == (2, 2, False, None)


@pytest.mark.parametrize(("cities_more", "places_more"), [(True, False), (False, True)])
def test_locations_that_may_have_more_have_no_total(cities_more: bool, places_more: bool) -> None:
    result = LocationSearchResult.of(
        LocationQuery("krak"),
        LocationMatches((place("Kraków"),), more=cities_more),
        LocationMatches((), more=places_more),
    )

    assert (result.total, result.returned, result.truncated) == (None, 1, True)
    assert result.hint == (
        "Pasujących lokalizacji może być więcej: doprecyzuj nazwę (np. dodaj miasto)."
    )


def test_no_locations_say_what_to_try() -> None:
    result = LocationSearchResult.of(
        LocationQuery("xyzzy"), LocationMatches(()), LocationMatches(())
    )

    assert (result.total, result.returned, result.truncated) == (0, 0, False)
    assert result.hint == (
        "Nic nie pasuje do 'xyzzy'. Sprawdź pisownię (z polskimi znakami) albo podaj początek "
        "nazwy miasta, dzielnicy lub ulicy."
    )


@pytest.mark.parametrize(
    ("kind", "district", "street", "name"),
    [
        ("district", "Mokotów", None, "Mokotów"),
        ("street", "Mokotów", "Puławska", "Puławska"),
        ("estate", "Mokotów", None, "Mokotów"),
        ("estate", None, None, "Warszawa"),
    ],
)
def test_a_place_is_named_after_what_it_is(
    kind: str, district: str | None, street: str | None, name: str
) -> None:
    located = Location.place(
        kind=kind,
        city="Warszawa",
        city_slug="warszawa",
        district=district,
        street=street,
        lat=None,
        lng=None,
        offer_count=None,
    )

    assert (located.kind, located.name) == (kind, name)
