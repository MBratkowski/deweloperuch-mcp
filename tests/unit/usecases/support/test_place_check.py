"""Tests of ``deweloperuch_mcp.usecases.support.place_check``."""

import pytest

from deweloperuch_mcp.models.errors import (
    DeweloperuchError,
    InvalidInputError,
    LimiterWaitError,
    NotFoundError,
    RateLimitedError,
    ServiceBlockedError,
    ServiceError,
    SessionClosedError,
    UnexpectedResponseError,
)
from deweloperuch_mcp.models.values import CitySlug
from deweloperuch_mcp.usecases.support.place_check import PlaceCheck
from support.fakes.places import VILLAGE, FakePlaces

DETAIL = "/api/x: HTTP 404"


def first_answer() -> NotFoundError:
    """The service's own "not found", as the use case words it."""
    return NotFoundError("Serwis nie zna miasta 'x'.", detail=DETAIL)


def not_found_in(places: FakePlaces, city: str, first: NotFoundError, **then: str) -> NotFoundError:
    """What a call ends with after the service answered ``first`` about ``city``."""
    with (
        pytest.raises(NotFoundError) as caught,
        PlaceCheck(places, CitySlug(city), what="statystyk rynku", **then),
    ):
        raise first
    return caught.value


def test_unknown_place_says_there_is_no_such_place() -> None:
    places, first = FakePlaces(), first_answer()

    found = not_found_in(places, "nieistniejace-miasto", first)

    assert str(found) == (
        "Nie znaleziono miejscowości o city_slug 'nieistniejace-miasto'. Jeśli slug nie pochodzi "
        "z search_locations, weź go stamtąd; jeśli pochodzi, serwis nie ma dla niej tych "
        "danych: powiedz to użytkownikowi i nie ponawiaj."
    )
    assert (found.detail, found.__cause__) == (DETAIL, first)
    assert places.calls == ["nieistniejace-miasto"]


def test_known_place_without_data_says_so() -> None:
    places, first = FakePlaces.knowing(VILLAGE), first_answer()

    found = not_found_in(places, "ignatki-osiedle", first)

    assert str(found) == (
        "Miejscowość 'Ignatki-osiedle' istnieje, ale serwis nie ma dla niej statystyk rynku. "
        "Nie ponawiaj; powiedz to użytkownikowi."
    )
    assert (found.detail, found.__cause__) == (DETAIL, first)
    assert places.calls == ["ignatki-osiedle"]


def test_known_place_ends_with_what_to_do_when_the_caller_says() -> None:
    places = FakePlaces.knowing(VILLAGE)

    found = not_found_in(places, "ignatki-osiedle", first_answer(), then="Spróbuj city=polska.")

    assert str(found).endswith("dla niej statystyk rynku. Spróbuj city=polska.")


def test_a_place_under_another_slug_proves_nothing() -> None:
    """The dictionary gave a place of another slug: whether the one asked for has data is
    not known, so the first answer stands."""
    first = first_answer()

    assert not_found_in(FakePlaces({"ignatki": VILLAGE}), "ignatki", first) is first


@pytest.mark.parametrize(
    "failure",
    [
        ServiceError("500"),
        UnexpectedResponseError("inny format"),
        NotFoundError("404"),
        LimiterWaitError("czekaj", 30.0),
        SessionClosedError("zamknięta"),
        InvalidInputError("poza listą"),
    ],
    ids=lambda failure: type(failure).__name__,
)
def test_lookup_failure_keeps_the_original_message(failure: DeweloperuchError) -> None:
    first = first_answer()

    assert not_found_in(FakePlaces(failure=failure), "nieistniejace-miasto", first) is first


@pytest.mark.parametrize(
    "stop",
    [ServiceBlockedError("STOP"), RateLimitedError("STOP 429", 60.0)],
    ids=lambda stop: type(stop).__name__,
)
def test_a_stop_of_the_lookup_is_never_hidden(stop: ServiceBlockedError) -> None:
    """A STOP is about the series of requests, not about the data (``ReportedAs``): the
    caller must see it, so it is not swallowed with the lookup's other failures."""
    with (
        pytest.raises(ServiceBlockedError) as caught,
        PlaceCheck(FakePlaces(failure=stop), CitySlug("x"), what="ofert"),
    ):
        raise first_answer()

    assert caught.value is stop


def test_a_successful_call_never_looks_up() -> None:
    places = FakePlaces.knowing(VILLAGE)

    with PlaceCheck(places, CitySlug("ignatki-osiedle"), what="ofert"):
        pass

    assert places.calls == []


@pytest.mark.parametrize(
    "error",
    [ServiceError("500"), UnexpectedResponseError("inny format"), ValueError("bug")],
    ids=lambda error: type(error).__name__,
)
def test_other_errors_pass_unchanged_without_a_lookup(error: Exception) -> None:
    places = FakePlaces.knowing(VILLAGE)

    with (
        pytest.raises(type(error)) as caught,
        PlaceCheck(places, CitySlug("ignatki-osiedle"), what="ofert"),
    ):
        raise error

    assert caught.value is error and places.calls == []
