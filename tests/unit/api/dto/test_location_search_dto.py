"""Tests of ``deweloperuch_mcp.api.dto.location_search_dto``."""

import pytest

from deweloperuch_mcp.api.dto.location_search_dto import LocationSearchDto, LocationSuggestionDto
from deweloperuch_mcp.models.location import Location, LocationMatches
from support.providers.samples import body


def test_district_and_street_locations() -> None:
    district, street = LocationSearchDto.model_validate(body("api.location_search")).suggestions

    assert district.to_model() == Location(
        kind="district",
        name="Mokotów",
        city="Warszawa",
        city_slug="warszawa",
        district="Mokotów",
        lat=52.189818153819054,
        lng=21.05171136865118,
        # [W] count read as the number of offers in the area (no `variant` sent).
        offer_count=1562,
    )
    located = street.to_model()
    assert (located.kind, located.name, located.district, located.street) == (
        "street",
        "Mokotów",
        "Mokotów",
        "Mokotów",
    )


def test_suggestion_of_unknown_kind_keeps_the_kind_and_a_name() -> None:
    suggestion = LocationSuggestionDto(kind="estate", city="Warszawa", citySlug="warszawa")

    located = suggestion.to_model()

    assert (located.kind, located.name) == ("estate", "Warszawa")


def test_coordinates_given_as_strings_become_numbers() -> None:
    suggestion = LocationSuggestionDto(
        kind="street", city="Sopot", citySlug="sopot", street="Morska", lat="54.4", lng=""
    )

    located = suggestion.to_model()

    assert (located.lat, located.lng) == (54.4, None)


@pytest.mark.parametrize(("limit", "more"), [(2, True), (3, False)])
def test_a_full_page_of_suggestions_may_hide_more(limit: int, more: bool) -> None:
    # [W] /api/location-search has no flag of its own: a full page may hide more.
    found = LocationSearchDto.model_validate(body("api.location_search")).to_model(limit)

    assert found == LocationMatches(found.items, more=more)
    assert [item.kind for item in found.items] == ["district", "street"]
