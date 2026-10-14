"""Contract of ``deweloperuch_mcp.api.dto.standalone_valuation_dto`` with the service's
real answers (the samples in docs/discovery/samples/, the raw payloads in
tests/fixtures/).
"""

import datetime as dt
import math
from typing import Any

import pytest

from deweloperuch_mcp.api.dto.standalone_valuation_dto import (
    StandaloneValuationDto,
    ValuationTransactionDto,
)
from deweloperuch_mcp.models.errors import UnexpectedResponseError
from deweloperuch_mcp.models.valuation import PRIMARY, SECONDARY, ComparableTransaction
from support.builders.valuation import SUBJECT, api_sample, mapped, parsed
from support.providers.samples import envelope, untrimmed


def report_sample() -> Any:
    return untrimmed(envelope("page.offer_report")["props"]["data"])


def haversine_m(lat: float, lng: float, other_lat: float, other_lng: float) -> float:
    north, east = math.radians(other_lat - lat), math.radians(other_lng - lng)
    h = (
        math.sin(north / 2) ** 2
        + math.cos(math.radians(lat)) * math.cos(math.radians(other_lat)) * math.sin(east / 2) ** 2
    )
    return 2 * 6_371_008.8 * math.asin(math.sqrt(h))


def test_the_api_sample_maps_to_the_valuation() -> None:
    valuation = mapped(api_sample())

    assert valuation.subject == SUBJECT
    assert valuation.estimated_value == 1_063_300
    assert valuation.price_per_m2 == 21_266
    assert valuation.radius_m == 200  # radiusKm 0.2
    assert valuation.period_months == 24
    stats = valuation.stats
    assert stats is not None
    assert (stats.count, stats.median_price_per_m2, stats.average_price_per_m2) == (9, 23830, 22195)
    assert (stats.min_price_per_m2, stats.max_price_per_m2) == (13187, 31492)
    assert len(valuation.comparables) == 3
    assert valuation.comparables[0] == ComparableTransaction(
        address="Ulica Nowogrodzka 38",
        date=dt.date(2025, 4, 17),
        price=765_002,
        area_m2=43.57,
        price_per_m2=17_558,
        floor=6,
        distance_m=150,
        market=SECONDARY,
        building_slug="ulica-nowogrodzka-38-warszawa",
        city_slug="warszawa",
    )


def test_the_offer_report_has_the_same_format() -> None:
    valuation = mapped(report_sample())

    assert (valuation.estimated_value, valuation.price_per_m2) == (1_003_230, 18_158)
    assert (valuation.radius_m, valuation.period_months) == (200, 24)
    assert valuation.stats is not None and valuation.stats.count == 26
    assert [c.distance_m for c in valuation.comparables] == [50, 100, 100]
    assert valuation.comparables[0].address == "Ulica Płosa 4"


@pytest.mark.parametrize("sample", [api_sample, report_sample])
def test_the_estimate_is_the_price_per_m2_times_the_area(sample: Any) -> None:
    """[P] in both samples: estimatedValue = estimatedPricePerSqm × area, rounded."""
    data = sample()

    assert round(data["estimatedPricePerSqm"] * data["area"]) == data["estimatedValue"]


@pytest.mark.parametrize("sample", [api_sample, report_sample])
def test_each_price_per_m2_is_the_price_over_the_area(sample: Any) -> None:
    for item in mapped(sample()).comparables:
        assert item.price is not None and item.area_m2 is not None
        assert item.price_per_m2 == round(item.price / item.area_m2)


@pytest.mark.parametrize("sample", [api_sample, report_sample])
def test_the_distance_is_in_metres_rounded_to_50(sample: Any) -> None:
    """[P] both samples: the distance from the point's coordinates, rounded to the nearest
    50 m (152 and 165 m -> 150, 42 -> 50, 93.5 and 119.8 -> 100)."""
    data = sample()

    for item in data["transactions"]:
        exact = haversine_m(
            data["latitude"], data["longitude"], item["latitude"], item["longitude"]
        )
        assert abs(exact - item["distance"]) <= 25, (item["address"], exact)
        assert item["distance"] % 50 == 0


@pytest.mark.parametrize(
    ("name", "where"),
    [("api.standalone_val", ("response",)), ("page.offer_report", ("props", "data"))],
)
def test_the_statistics_count_every_comparable_transaction(
    name: str, where: tuple[str, ...]
) -> None:
    """[W] what the statistics cover: in both samples their count is the number of the
    service's transactions (the total of the trimmed list, 9 and 26), and no transaction
    is excluded, so whether excluded ones count is not known."""
    data: Any = envelope(name)
    for key in where:
        data = data[key]
    marker = data["transactions"][-1]
    total = int(marker.removesuffix(" total)").rsplit(" ", 1)[1])

    assert data["stats"]["count"] == total
    assert not any(item["excluded"] for item in data["transactions"][:-1])


def test_the_working_data_of_the_service_is_not_read() -> None:
    """D5: radiusPool, estimationContext and buildings stay out of the DTO and the domain;
    so do fields whose meaning is not confirmed."""
    read = set(StandaloneValuationDto.model_fields)
    read_of_an_item = set(ValuationTransactionDto.model_fields)
    left_out = {"radiusPool", "estimationContext", "buildings", "trendMonthlyPct", "areaElasticity"}
    left_out_of_an_item = {"excluded", "isSamePrimaryInvestment", "unitNumber", "saleRcnId"}

    assert read.isdisjoint(left_out)
    assert read_of_an_item.isdisjoint(left_out_of_an_item)
    assert "radiusPool" in api_sample()  # the sample does have it


@pytest.mark.parametrize("missing", ["estimatedValue", "estimatedPricePerSqm", "transactions"])
def test_a_renamed_field_breaks_the_contract(missing: str) -> None:
    data = api_sample()
    del data[missing]

    with pytest.raises(UnexpectedResponseError, match="Serwis mógł się zmienić"):
        parsed(data)


def test_values_as_text_and_empty_values_are_tolerated() -> None:
    data = api_sample()
    data["estimatedPricePerSqm"] = "21266"
    data["radiusKm"] = "0.5"
    item = data["transactions"][0]
    item.update(address="", floor="parter", marketType="", distance="150", date="")

    valuation = mapped(data)
    first = valuation.comparables[0]

    assert valuation.price_per_m2 == 21266 and valuation.radius_m == 500
    assert (first.address, first.floor, first.market, first.date) == (None, None, None, None)
    assert first.distance_m == 150


@pytest.mark.parametrize(
    ("floor", "expected"), [("6", 6), (" -1 ", -1), (3, 3), (2.0, 2), (2.5, None), ("", None)]
)
def test_floors(floor: object, expected: int | None) -> None:
    data = api_sample()
    data["transactions"][0]["floor"] = floor

    assert mapped(data).comparables[0].floor == expected


@pytest.mark.parametrize(
    ("market", "expected"),
    [("pierwotny", PRIMARY), ("wtorny", SECONDARY), ("Inny", "inny"), (None, None)],
)
def test_markets_in_the_domain_words(market: str | None, expected: str | None) -> None:
    data = api_sample()
    data["transactions"][0]["marketType"] = market

    assert mapped(data).comparables[0].market == expected


def test_a_valuation_without_an_estimate() -> None:
    """[H] how the service answers a point without transactions; a null estimate and no
    transactions are read as such, not as a broken contract."""
    data = api_sample()
    data.update(estimatedValue=None, estimatedPricePerSqm=None, stats=None, transactions=[])

    valuation = mapped(data)

    assert not valuation.estimated
    assert valuation.stats is None and valuation.comparables == ()
