"""Contract of ``deweloperuch_mcp.api.dto.city_sales_dto`` with the service's real answers
(the samples in docs/discovery/samples/, the raw payloads in tests/fixtures/).
"""

import collections
import json
import statistics
from typing import Any

import pytest

from deweloperuch_mcp.api.dto.city_sales_dto import CitySalesDto
from deweloperuch_mcp.models.market_statistics import MarketCriteria
from deweloperuch_mcp.models.values import CitySlug
from support.providers.rsc import CITY_SALES
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
