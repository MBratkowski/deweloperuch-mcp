"""Tests of ``deweloperuch_mcp.api.dto.building_dto``."""

import datetime as dt
from typing import Any

import pytest
import respx

from deweloperuch_mcp.api.adapters.buildings_api import BuildingsApi
from deweloperuch_mcp.api.dto.building_dto import BuildingDto, TransactionDto, UnitDto
from deweloperuch_mcp.api.http.transport import HttpClient
from deweloperuch_mcp.models.building import (
    BuildingSlug,
    Transaction,
)
from deweloperuch_mcp.models.errors import (
    UnexpectedResponseError,
)
from support.providers.routes.buildings import (
    BUILDING,
    BUILDING_ID,
    CISNA_BODY,
    SLUG,
    TREND,
    building_routes,
    fixture_body,
)
from support.providers.samples import body

DAY = dt.date(2025, 11, 17)


def building_dto(data: Any = None) -> BuildingDto:
    return BuildingDto.model_validate(body("api.tx_visible") if data is None else data)


def transaction_dto(**changes: Any) -> TransactionDto:
    data = body("api.tx_visible")["sale"][0]["sale_event_rcn"][0]
    data.update(changes)
    return TransactionDto.model_validate(data)


def test_the_building_of_the_sample() -> None:
    building = building_dto().to_model()

    assert (building.building_id, building.building_slug, building.name) == (
        BUILDING_ID,
        SLUG,
        "23 Marca 79C",
    )
    assert (building.city, building.city_slug, building.street) == (
        "Sopot",
        "sopot",
        "23 Marca 79C",
    )
    assert (building.lat, building.lng) == (54.44705851, 18.54342128)
    assert (building.avg_price, building.avg_area_m2, building.avg_price_per_m2) == (
        1324114.66,
        61.6,
        21494.72,
    )
    assert [unit.unit_id for unit in building.units] == [477553, 477335, 477334]
    first = building.units[0]
    assert (first.name, first.floor, first.rooms, first.area_m2) == (
        "226401_4.4191.4568_BUD.3_LOK",
        1,
        5,
        122.01,
    )
    assert first.transactions == (
        Transaction(
            date=DAY,
            price=1900000.47,
            price_per_m2=15572.5,
            currency="PLN",
            market="primary",
            classification="regular",
            buyer="natural_person",
            seller="legal_person",
            share="1/1",
        ),
    )
    assert first.transactions[0].whole_unit


def test_the_averages_are_the_services_own() -> None:
    """[W] ``avg_amount``, ``avg_size`` and ``avg_price_sqm`` are means over the building
    (their names say so; the sample's 3 of 86 units cannot show it): they are passed on
    as the service gives them, number or text, never recomputed from the units."""
    data = body("api.tx_visible")
    assert (data["avg_amount"], data["avg_size"], data["avg_price_sqm"]) == (
        1324114.66,
        61.6,
        21494.72,
    )
    data.update(avg_amount="1324114.66", avg_size="61.6", avg_price_sqm="")

    building = building_dto(data).to_model()

    assert (building.avg_price, building.avg_area_m2, building.avg_price_per_m2) == (
        1324114.66,
        61.6,
        None,
    )
    shown = [t.price for unit in building.units for t in unit.transactions]
    assert sum(p for p in shown if p is not None) / len(shown) != building.avg_price


@pytest.mark.parametrize(
    ("field", "attribute"),
    [
        ("avg_amount", "avg_price"),
        ("avg_size", "avg_area_m2"),
        ("avg_price_sqm", "avg_price_per_m2"),
    ],
)
@pytest.mark.parametrize("zero", [0, "0", 0.0, -1], ids=["0", "text 0", "0.0", "-1"])
def test_an_average_of_0_or_less_is_no_average(field: str, attribute: str, zero: object) -> None:
    """A rule test on a hand-edited payload: the real building cisna
    (tests/fixtures/api/) with one of its averages replaced by 0 or less. [W] no real
    building with such an average is known; the service writes 0 for no value in its
    monthly statistics and ``city-transaction-stats`` [P], and no flat costs 0."""
    data = fixture_body(CISNA_BODY)
    data[field] = zero

    building = building_dto(data).to_model()

    assert getattr(building, attribute) is None
    others = {"avg_price", "avg_area_m2", "avg_price_per_m2"} - {attribute}
    assert all(getattr(building, other) > 0 for other in others)


@pytest.mark.parametrize(("name", "expected"), [("", None), ("  ", None), (" Rynek 1 ", "Rynek 1")])
def test_a_blank_name_is_no_address(name: str, expected: str | None) -> None:
    """A rule test on hand-edited payloads: the sample with its name replaced; the
    building cisna sends ``""`` [P 2026-10-15] (tests/contract)."""
    data = body("api.tx_visible")
    data["name"] = name

    assert building_dto(data).to_model().name == expected


@pytest.mark.parametrize(
    ("changes", "attribute", "word"),
    [
        (dict(marketType="wtorny"), "market", "secondary"),
        (dict(marketType="nowy_rynek"), "market", "nowy_rynek"),
        (dict(classification="udzial"), "classification", "share"),
        (dict(classification="hurt"), "classification", "bulk"),
        (dict(classification="rzadowa"), "classification", "government"),
        (dict(classification="egzekucja"), "classification", "enforcement"),
        (dict(classification="bonifikata"), "classification", "discount"),
        (dict(classification="anomalia_down"), "classification", "anomaly_low"),
        (dict(classification="anomalia_up"), "classification", "anomaly_high"),
        (dict(classification="nowa_klasa"), "classification", "nowa_klasa"),
        (dict(buyerType="osobaPrawna"), "buyer", "legal_person"),
        (dict(sellerType="osobaFizyczna"), "seller", "natural_person"),
        (dict(sellerType="skarbPanstwa"), "seller", "skarbPanstwa"),
        (dict(sellerType=""), "seller", None),
        (dict(participation="1/2"), "share", "1/2"),
        (dict(participation=None), "share", None),
        (dict(currency=""), "currency", None),
        (dict(amount=1900000), "price", 1900000.0),
        (dict(amount=""), "price", None),
        (dict(amount_sqm="15572.497910007376"), "price_per_m2", 15572.497910007376),
        (dict(creation_date="2025-11-17T00:00:00.000Z"), "date", DAY),
        (dict(creation_date=""), "date", None),
    ],
)
def test_values_of_the_service_become_the_domains(
    changes: dict[str, Any], attribute: str, word: object
) -> None:
    """Known values become the domain's words; unknown ones pass unchanged (D3)."""
    assert getattr(transaction_dto(**changes).to_model(), attribute) == word


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        (dict(floor_number="3", rooms_number="2", size="55.25"), (3, 2, 55.25)),
        (dict(floor_number=0, rooms_number=None, size=None), (0, None, None)),
        (dict(floor_number=-1, rooms_number="", size=""), (-1, None, None)),
        (dict(floor_number=1.5, rooms_number=2.0, size=40), (None, 2, 40.0)),
    ],
)
def test_floors_rooms_and_areas_as_numbers_or_text(
    changes: dict[str, Any], expected: tuple[object, ...]
) -> None:
    data = body("api.tx_visible")["sale"][0]
    data.update(changes)

    unit = UnitDto.model_validate(data).to_model()

    assert (unit.floor, unit.rooms, unit.area_m2) == expected


@pytest.mark.parametrize(
    ("changes", "expected"),
    [
        # As the building cisna sends it [P 2026-10-15] (tests/contract).
        (dict(floor="", floor_number=0), (None, 5)),
        (dict(floor="0", floor_number=0), (0, 5)),
        # Stated as a number instead of text: still stated.
        (dict(floor=2, floor_number=2), (2, 5)),
        (dict(floor=2.0, floor_number="2", rooms=5), (2, 5)),
        # [W] rooms have the same pair of fields; no blank one has been seen.
        (dict(rooms=" ", rooms_number=0), (1, None)),
        (dict(floor=None, rooms=None), (None, None)),
    ],
)
def test_a_floor_or_rooms_the_register_leaves_blank_are_unknown(
    changes: dict[str, Any], expected: tuple[object, ...]
) -> None:
    """A rule test on hand-edited payloads: the sample's first unit (``floor`` "1",
    ``rooms`` "5") with the text of its floor or rooms blanked. The service then sends
    0 as the number, which is no ground floor and no count of rooms."""
    data = body("api.tx_visible")["sale"][0]
    data.update(changes)

    unit = UnitDto.model_validate(data).to_model()

    assert (unit.floor, unit.rooms) == expected


def test_the_transactions_of_a_unit_oldest_first() -> None:
    data = body("api.tx_visible")["sale"][0]
    deed = data["sale_event_rcn"][0]
    data["sale_event_rcn"] = [
        dict(deed, sale_event_rcn_id=3, creation_date="2025-11-17", amount="3"),
        dict(deed, sale_event_rcn_id=2, creation_date="2019-05-02", amount="2"),
        dict(deed, sale_event_rcn_id=1, creation_date="2025-11-17", amount="1"),
    ]

    unit = UnitDto.model_validate(data).to_model()

    assert [t.price for t in unit.transactions] == [2.0, 1.0, 3.0]
    assert unit.last_sold_on == DAY


def test_the_catalog_asks_for_the_building_then_its_trend_by_number(
    http: HttpClient, service: respx.MockRouter
) -> None:
    building_route, trend_route = building_routes(service)
    catalog = BuildingsApi(http)

    building = catalog.building(BuildingSlug(SLUG))
    trend = catalog.neighbourhood_trend(building)

    assert building == building_dto().to_model()
    assert [q.period for q in trend.quarters] == ["2006-Q2", "2006-Q3", "2006-Q4"]
    for route in (building_route, trend_route):
        assert route.call_count == 1
        assert route.calls.last.request.headers["accept"] == "application/json"
    assert str(building_route.calls.last.request.url) == BUILDING
    assert str(trend_route.calls.last.request.url) == TREND


def test_a_trend_of_another_shape_is_an_unexpected_response(
    http: HttpClient, service: respx.MockRouter
) -> None:
    service.get(TREND).respond(200, json=dict(data=[dict(period="2006")]))
    building = building_dto().to_model()

    with pytest.raises(UnexpectedResponseError):
        BuildingsApi(http).neighbourhood_trend(building)
