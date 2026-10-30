"""Contract of ``deweloperuch_mcp.api.dto.city_sales_dto`` with the service's real answers
(the samples in docs/discovery/samples/, the raw payloads in tests/fixtures/).
"""

import collections
import json
import statistics
from typing import Any

import pytest

from deweloperuch_mcp.api.dto.city_sales_dto import CitySalesDto, OfferSnapshotDto
from deweloperuch_mcp.api.dto.dto import Dto
from deweloperuch_mcp.errors import UnexpectedResponseError
from deweloperuch_mcp.models.market_statistics import MarketCriteria
from deweloperuch_mcp.models.values import CitySlug
from support.providers.rsc import CITY_SALES, OFFER_SNAPSHOT_WROCLAW
from support.providers.samples import body


def city_sales(city: str) -> Any:
    """The real body of ``city-sales`` (tests/fixtures/api/), whole."""
    return json.loads(CITY_SALES[city].read_bytes())


@pytest.mark.parametrize("data", [body("api.city_sales_sopot"), "sopot", "krakow"])
def test_city_sales_sample_and_fixtures(data: Any) -> None:
    parsed = CitySalesDto.model_validate(city_sales(data) if isinstance(data, str) else data)

    assert parsed.sales and parsed.investments
    assert {sale.status for sale in parsed.sales} == {"active"}  # [P] active offers only


def test_city_sales_of_krakow_hold_what_the_fixture_readme_says() -> None:
    parsed = CitySalesDto.model_validate(city_sales("krakow"))

    assert (len(parsed.investments), len(parsed.sales)) == (143, 7325)
    assert len({item.developerSlug for item in parsed.investments}) == 67
    known = {item.id for item in parsed.investments}
    assert all(sale.investId in known for sale in parsed.sales)


def test_the_price_per_m2_of_city_sales_is_the_one_the_domain_derives() -> None:
    """[P 2026-10-13] ``priceSqm`` = ``amount / size`` to 0.01 for every offer of Kraków, so
    the summary derives it as search results do (``priceSqm`` is not read)."""
    sales = city_sales("krakow")["sales"]

    assert all(abs(s["amount"] / s["size"] - s["priceSqm"]) <= 0.01 for s in sales)


def test_the_market_of_krakow_from_the_real_dump() -> None:
    """The summary of every offer of the fixture, against the standard library."""
    sales = city_sales("krakow")
    offers = CitySalesDto.model_validate(sales).to_model(CitySlug("krakow"))

    result = offers.statistics(MarketCriteria(city=CitySlug("krakow")))

    prices = [float(s["amount"]) for s in sales["sales"]]
    areas = [float(s["size"]) for s in sales["sales"]]
    assert (result.offers, result.investments, result.developers) == (7325, 143, 67)
    for spread, values in ((result.price_spread, prices), (result.area_spread, areas)):
        quartiles = statistics.quantiles(values, n=4, method="inclusive")
        assert spread is not None
        assert (spread.min, spread.max) == (min(values), max(values))
        assert spread.p25 == pytest.approx(quartiles[0])
        assert spread.median == pytest.approx(statistics.median(values))
        assert spread.p75 == pytest.approx(quartiles[2])
    developer_of = {item["id"]: item["developerSlug"] for item in sales["investments"]}
    counts = collections.Counter(developer_of[s["investId"]] for s in sales["sales"])
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:10]
    assert [(d.developer_slug, d.offers) for d in result.top_developers] == ranked


# --- offer-snapshot (since the 2.0 build) ---------------------------------------------------


def wroclaw() -> Any:
    """The real body of ``offer-snapshot/wroclaw`` of 2026-10-30, whole."""
    return json.loads(OFFER_SNAPSHOT_WROCLAW.read_bytes())


def test_offer_snapshot_fixture() -> None:
    """The sample ``api.offer_snapshot_wroclaw`` trims each row to 3 numbers, so only the
    whole body of the fixture can be read."""
    snapshot = OfferSnapshotDto.model_validate(wroclaw())

    parsed = snapshot.city_sales("/api/map/offer-snapshot/wroclaw")

    assert parsed.sales and parsed.investments
    assert {sale.status for sale in parsed.sales} == {"active"}  # status 0 in every row
    known = {item.id for item in parsed.investments}
    assert all(sale.investId in known for sale in parsed.sales)


def test_the_columns_of_a_snapshot_row() -> None:
    """[P 2026-10-30] ``[id, investId, status, amount, priceSqm, size, change]``: the
    price per m² is ``amount / size`` to 0.01 in every row, so the domain derives it."""
    rows = wroclaw()["sales"]

    assert {len(row) for row in rows} == {7}
    assert all(abs(row[3] / row[5] - row[4]) <= 0.01 for row in rows)
    first = OfferSnapshotDto.model_validate(wroclaw()).city_sales("/x").sales[0]
    assert (first.id, first.investId, first.amount, first.size) == tuple(
        rows[0][i] for i in (0, 1, 3, 5)
    )


def test_the_market_of_wroclaw_is_the_one_the_service_states() -> None:
    """[P 2026-10-30] the summary of ``/statystyki/wroclaw/oferty`` the same day: 5,836
    offers, 110 investments, 46 developers, median 14,600 PLN/m², Develia 818 offers."""
    city = CitySlug("wroclaw")
    offers = OfferSnapshotDto.model_validate(wroclaw()).city_sales("/x").to_model(city)

    result = offers.statistics(MarketCriteria(city=city))

    assert (result.offers, result.investments, result.developers) == (5836, 110, 46)
    assert result.price_per_m2_spread is not None
    assert result.price_per_m2_spread.median == 14600
    assert (result.top_developers[0].developer_slug, result.top_developers[0].offers) == (
        "develia",
        818,
    )


def test_a_short_snapshot_row_does_not_match_the_contract() -> None:
    data = {"citySlug": "x", "investments": [], "sales": [[1, 2, 0, 500000]]}

    with pytest.raises(UnexpectedResponseError):
        Dto.validated(OfferSnapshotDto, data, "/api/map/offer-snapshot/x")
