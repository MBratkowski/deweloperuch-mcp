"""Tests of ``deweloperuch_mcp.usecases.get_building``."""

from typing import Any

import pytest

from deweloperuch_mcp.models.building import BuildingSlug, UnitsLimit
from deweloperuch_mcp.models.errors import (
    InvalidInputError,
    InvalidValueError,
    NotFoundError,
    ServiceError,
)
from deweloperuch_mcp.usecases.get_building import SLUG_SOURCE, GetBuilding, GetBuildingRequest
from support.fakes.buildings import FakeBuildingCatalog, FakeBuildingLinks
from support.providers.routes.buildings import SLUG


def test_a_building_without_its_trend_is_one_request() -> None:
    catalog = FakeBuildingCatalog()

    found = GetBuilding(catalog, FakeBuildingLinks()).execute(
        GetBuildingRequest(building_slug=BuildingSlug(SLUG), limit=UnitsLimit(2))
    )

    assert catalog.calls == [f"building {SLUG}"]
    assert [unit.unit_id for unit in found.listing.units] == [2, 3]
    assert found.listing.omitted == 1
    assert found.trend is None
    assert found.building_url == "building:miasto:ulica-1-miasto"


def test_the_trend_when_asked_for_its_newest_quarters() -> None:
    catalog = FakeBuildingCatalog()

    found = GetBuilding(catalog, FakeBuildingLinks()).execute(
        GetBuildingRequest(building_slug=BuildingSlug(SLUG), include_trend=True, trend_quarters=2)
    )

    assert catalog.calls == [f"building {SLUG}", "trend 1"]
    assert found.trend is not None
    assert [q.period for q in found.trend.quarters] == ["2025-Q1", "2025-Q2"]
    assert found.trend.total == 3
    assert len(found.listing.units) == 3


def test_an_unknown_building_says_where_slugs_come_from() -> None:
    catalog = FakeBuildingCatalog(building_error=NotFoundError("HTTP 404", detail="/x"))

    with pytest.raises(NotFoundError) as caught:
        GetBuilding(catalog, FakeBuildingLinks()).execute(
            GetBuildingRequest(building_slug=BuildingSlug("nie-ma"), include_trend=True)
        )

    assert str(caught.value) == f"Nie znaleziono budynku 'nie-ma'. {SLUG_SOURCE}"
    assert caught.value.detail == "/x"
    assert catalog.calls == ["building nie-ma"]
    assert "/ceny-" not in str(caught.value) and "/api" not in str(caught.value)


def test_failures_of_the_trend_name_the_trend() -> None:
    catalog = FakeBuildingCatalog(
        trend_error=ServiceError("Serwis odpowiedział błędem HTTP 500.", 3.0)
    )

    with pytest.raises(ServiceError) as caught:
        GetBuilding(catalog, FakeBuildingLinks()).execute(
            GetBuildingRequest(building_slug=BuildingSlug(SLUG), include_trend=True)
        )

    assert str(caught.value) == (
        f"Trend cen w okolicy budynku '{SLUG}': Serwis odpowiedział błędem HTTP 500."
    )
    assert caught.value.pause_seconds == 3.0


def test_a_missing_trend_says_to_ask_without_it() -> None:
    catalog = FakeBuildingCatalog(trend_error=NotFoundError("HTTP 404"))

    with pytest.raises(NotFoundError, match="Pobierz budynek bez include_trend"):
        GetBuilding(catalog, FakeBuildingLinks()).execute(
            GetBuildingRequest(building_slug=BuildingSlug(SLUG), include_trend=True)
        )


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (
            # Where slugs come from is said by the tool's description and the not-found
            # message only (two places); a refusal says what a slug looks like.
            lambda: GetBuildingRequest.parse(building_slug="23-Marca"),
            "building_slug: oczekiwano slug budynku: małe litery bez polskich znaków, cyfry i "
            "myślniki, np. 23-marca-79c-sopot; podano '23-Marca'.",
        ),
        (
            lambda: GetBuildingRequest.parse(building_slug=SLUG, limit=-1),
            "limit musi być liczbą całkowitą z zakresu 0–100000 (liczba lokali w wyniku), "
            "podano -1.",
        ),
        (
            lambda: GetBuildingRequest.parse(building_slug=SLUG, include_trend="yes"),
            "include_trend musi być true albo false, podano 'yes'.",
        ),
        # Checked in the order of the parameters: the slug, the limit, the trend.
        (
            lambda: GetBuildingRequest.parse(building_slug="X", limit=-1, include_trend="x"),
            "building_slug: ",
        ),
        (
            lambda: GetBuildingRequest.parse(building_slug=SLUG, limit=-1, include_trend="x"),
            "limit musi",
        ),
    ],
)
def test_a_refusal_names_the_parameter_and_what_to_give(call: Any, message: str) -> None:
    with pytest.raises(InvalidInputError) as caught:
        call()

    assert str(caught.value).startswith(message)
    assert isinstance(caught.value.__cause__, InvalidValueError)


def test_the_arguments_of_a_building() -> None:
    assert GetBuildingRequest.parse(
        building_slug=f" {SLUG} ", limit=2, include_trend=True
    ) == GetBuildingRequest(
        building_slug=BuildingSlug(SLUG), limit=UnitsLimit(2), include_trend=True
    )
    assert GetBuildingRequest.parse(building_slug=SLUG) == GetBuildingRequest(
        building_slug=BuildingSlug(SLUG), limit=None, include_trend=False
    )
