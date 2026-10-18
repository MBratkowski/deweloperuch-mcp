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
from deweloperuch_mcp.models.valuation import (
    PRIMARY,
    SECONDARY,
    ComparableTransaction,
    PricePerM2Stats,
)
from deweloperuch_mcp.usecases.estimate_property_value import EstimatePropertyValueResult
from support.builders.valuation import CISNA_SUBJECT, SUBJECT, api_sample, mapped, parsed
from support.providers.routes.valuation import cisna
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
    so do fields whose meaning is not confirmed (radiusLevel: only its values are)."""
    read = set(StandaloneValuationDto.model_fields)
    read_of_an_item = set(ValuationTransactionDto.model_fields)
    left_out = {
        "radiusPool",
        "estimationContext",
        "buildings",
        "trendMonthlyPct",
        "areaElasticity",
        "radiusLevel",
    }
    left_out_of_an_item = {"excluded", "isSamePrimaryInvestment", "unitNumber", "saleRcnId"}

    assert read.isdisjoint(left_out)
    assert read_of_an_item.isdisjoint(left_out_of_an_item)
    assert "radiusPool" in api_sample()  # the sample does have it


def test_cisna_is_an_estimate_from_2_transactions_at_the_widest_radius() -> None:
    """[P 2026-10-15] tests/fixtures/api/standalone_val_cisna_20261015.json: the service
    widened the radius to its ceiling (radiusKm 1, radiusCeilingM 1000) and still found 2
    transactions; the estimate is their mean. Both reasons of low confidence apply."""
    valuation = mapped(cisna(), CISNA_SUBJECT)

    assert (valuation.estimated_value, valuation.price_per_m2) == (202_000, 4_040)
    assert (valuation.radius_m, valuation.radius_ceiling_m) == (1000, 1000)
    assert valuation.period_months == 24
    assert valuation.stats == PricePerM2Stats(
        count=2,
        median_price_per_m2=4040,
        average_price_per_m2=4040,
        min_price_per_m2=2302,
        max_price_per_m2=5778,
    )
    assert [c.price_per_m2 for c in valuation.comparables] == [2302, 5778]
    assert (valuation.few_comparables, valuation.at_widest_radius) == (True, True)
    assert valuation.low_confidence is True


@pytest.mark.parametrize("sample", [api_sample, report_sample])
def test_the_samples_are_not_of_low_confidence(sample: Any) -> None:
    """[P 2026-10-09] 9 and 26 transactions from 200 m, below the ceiling of 1000 m."""
    valuation = mapped(sample())

    assert (valuation.radius_m, valuation.radius_ceiling_m) == (200, 1000)
    assert valuation.counted_comparables in (9, 26)
    assert valuation.low_confidence is False


@pytest.mark.parametrize("zero", [0, "0", -1])
def test_prices_of_0_and_less_are_no_estimate(zero: object) -> None:
    """A rule test on the sample with its prices replaced by hand: the service has not been
    seen sending 0 here ([H]), but no flat costs 0 (``Dto._positive``). The count of
    transactions is no price: 0 stays a count."""
    data = api_sample()
    data.update(estimatedValue=zero, estimatedPricePerSqm=zero)
    for price in ("averagePricePerSqm", "medianPricePerSqm", "minPricePerSqm", "maxPricePerSqm"):
        data["stats"][price] = zero
    data["stats"]["count"] = 0

    valuation = mapped(data)

    assert (valuation.estimated, valuation.price_per_m2) == (False, None)
    assert valuation.stats == PricePerM2Stats(count=0)
    assert valuation.low_confidence is False  # no estimate: NO_ESTIMATE says what to do


@pytest.mark.parametrize(
    "missing",
    [
        dict(estimatedPricePerSqm=0),
        dict(estimatedPricePerSqm=None),
        dict(estimatedValue=0),
        dict(estimatedValue=""),
    ],
    ids=str,
)
def test_the_value_and_the_price_per_m2_are_one_estimate(missing: dict[str, object]) -> None:
    """A rule test on the sample edited by hand: [P] both samples give the value and the
    price per m² together, so one without the other is no estimate (never a value of null
    next to a price per m²)."""
    data = api_sample()
    data.update(missing)

    valuation = mapped(data)

    assert (valuation.estimated_value, valuation.price_per_m2) == (None, None)


@pytest.mark.parametrize("ceiling", [0, "0", 0.4, None, ""])
def test_a_ceiling_of_0_or_none_is_no_ceiling(ceiling: object) -> None:
    """A rule test on the sample edited by hand (1000 in every capture): a ceiling that
    rounds to 0 m, or none, never makes the radius the widest."""
    data = api_sample()
    data["radiusCeilingM"] = ceiling

    valuation = mapped(data)
    found = EstimatePropertyValueResult(listing=valuation.nearest())

    assert valuation.radius_ceiling_m is None and not valuation.at_widest_radius
    assert found.caveat() is None and found.hint is None


@pytest.mark.parametrize(
    "missing", ["estimatedValue", "estimatedPricePerSqm", "radiusCeilingM", "transactions"]
)
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
