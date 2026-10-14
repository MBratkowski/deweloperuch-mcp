"""Tests of ``deweloperuch_mcp.usecases.search_locations``."""

import pytest

from deweloperuch_mcp.models.errors import (
    InvalidInputError,
    ServiceError,
)
from deweloperuch_mcp.models.values import (
    LocationQuery,
)
from deweloperuch_mcp.usecases.search_locations import SearchLocations, SearchLocationsRequest
from support.fakes.catalogs import (
    FakeCatalogs,
)


def test_locations_ask_cities_then_districts_and_streets() -> None:
    fake = FakeCatalogs()
    request = SearchLocationsRequest(query=LocationQuery("krak"))

    result = SearchLocations(fake).execute(request).found

    assert fake.calls == ["cities", "districts_and_streets"]
    assert [item.name for item in result.items] == ["Kraków"]
    assert (result.total, result.truncated) == (None, True)


@pytest.mark.parametrize(
    ("failing", "subject"),
    [("cities", "Wyszukiwanie miast"), ("districts_and_streets", "Wyszukiwanie dzielnic i ulic")],
)
def test_a_location_source_failure_names_the_search(failing: str, subject: str) -> None:
    fake = FakeCatalogs(errors={failing: ServiceError("Serwis odpowiedział błędem HTTP 500.", 3.0)})

    with pytest.raises(ServiceError) as caught:
        SearchLocations(fake).execute(SearchLocationsRequest(query=LocationQuery("krak")))

    assert type(caught.value) is ServiceError
    assert str(caught.value) == f"{subject}: Serwis odpowiedział błędem HTTP 500."
    assert caught.value.pause_seconds == 3.0


def test_the_location_query_keeps_its_wording() -> None:
    with pytest.raises(InvalidInputError) as caught:
        SearchLocationsRequest.parse(query="k")

    assert str(caught.value) == (
        "query: podaj od 2 do 100 znaków nazwy miasta, dzielnicy lub ulicy, podano 'k'."
    )
