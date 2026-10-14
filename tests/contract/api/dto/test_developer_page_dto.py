"""Contract of ``deweloperuch_mcp.api.dto.developer_page_dto`` with the service's real
answers (the samples in docs/discovery/samples/, the raw payloads in tests/fixtures/).
"""

from pathlib import Path
from typing import Any

import pytest

from deweloperuch_mcp.api.dto import developer_page_dto
from deweloperuch_mcp.flight import component_props
from support.providers.rsc import DEVELOPER_POLSKA, DEVELOPER_WARSZAWA, raw


def developer_props(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """The object prop ``data`` and the list prop ``sale`` of a real profile."""
    props = list(component_props(raw(path)))
    data = next(value for name, value in props if name == "data" and isinstance(value, dict))
    sale = next(value for name, value in props if name == "sale" and isinstance(value, list))
    return data, sale


PROFILES = {"warszawa": DEVELOPER_WARSZAWA, "polska": DEVELOPER_POLSKA}


def active_sales(sale: list[dict[str, Any]], slugs: set[str] | None = None) -> list[Any]:
    return [
        s
        for s in sale
        if s["status"] == "active" and (slugs is None or s["investmentSlug"] in slugs)
    ]


def mean(values: list[float]) -> float:
    return sum(values) / len(values)


@pytest.mark.parametrize("city", PROFILES)
def test_the_developer_profile_parses(city: str) -> None:
    data, _ = developer_props(PROFILES[city])

    parsed = developer_page_dto.DeveloperPageDto.model_validate(data)

    assert (parsed.developer.slug, parsed.developer.name) == ("atal", "ATAL S.A.")
    assert parsed.developer.website == ""  # empty: not shown
    assert len(parsed.investments) == {"warszawa": 4, "polska": 42}[city]
    assert len(parsed.citiesStats) == 14


@pytest.mark.parametrize("city", PROFILES)
def test_total_projects_are_the_investments_listed(city: str) -> None:
    data, _ = developer_props(PROFILES[city])

    assert data["filteredStats"]["totalProjects"] == len(data["investments"])
    assert all(
        item["status"] == "active" and item["active_offers"] > 0 for item in data["investments"]
    )


@pytest.mark.parametrize("city", PROFILES)
def test_total_sales_are_the_active_offers(city: str) -> None:
    """``totalSales`` = Σ ``active_offers`` = the active offers of ``sale`` (not every
    offer: Σ ``total_offers`` is the length of ``sale``)."""
    data, sale = developer_props(PROFILES[city])
    investments = data["investments"]

    assert data["filteredStats"]["totalSales"] == sum(i["active_offers"] for i in investments)
    assert data["filteredStats"]["totalSales"] == len(active_sales(sale))
    assert sum(i["total_offers"] for i in investments) == len(sale)


@pytest.mark.parametrize("city", PROFILES)
def test_total_cities_are_the_cities_of_the_investments(city: str) -> None:
    data, _ = developer_props(PROFILES[city])

    cities = {item["city_slug"] for item in data["investments"]}
    assert data["filteredStats"]["totalCities"] == len(cities)


@pytest.mark.parametrize("city", PROFILES)
def test_the_averages_are_those_of_the_active_offers(city: str) -> None:
    """``averagePrice`` is the mean price of the active offers (rounded); ``averageSize``
    their mean area (to 0.01 m²); ``avgAmountPerM2`` the investments' price per m²
    weighted by their active offers (rounded)."""
    data, sale = developer_props(PROFILES[city])
    stats, investments = data["filteredStats"], data["investments"]
    active = active_sales(sale)

    assert stats["averagePrice"] == round(mean([float(s["amount"]) for s in active]))
    assert stats["averageSize"] == pytest.approx(mean([float(s["size"]) for s in active]), abs=0.01)
    weighted = sum(i["avg_price_sqm"] * i["active_offers"] for i in investments)
    assert stats["avgAmountPerM2"] == round(weighted / stats["totalSales"])


@pytest.mark.parametrize("city", PROFILES)
def test_each_investment_counts_its_offers_and_averages_its_active_ones(city: str) -> None:
    data, sale = developer_props(PROFILES[city])

    for item in data["investments"]:
        mine = [s for s in sale if s["investmentSlug"] == item["slug"]]
        active = active_sales(mine)
        assert (item["total_offers"], item["active_offers"]) == (len(mine), len(active))
        assert item["avg_amount"] == pytest.approx(
            mean([float(s["amount"]) for s in active]), abs=0.01
        )
        assert item["avg_size"] == pytest.approx(mean([float(s["size"]) for s in active]), abs=0.01)


def test_the_cities_are_every_city_of_the_developer_whatever_the_page() -> None:
    warszawa, _ = developer_props(DEVELOPER_WARSZAWA)
    polska, _ = developer_props(DEVELOPER_POLSKA)

    assert warszawa["citiesStats"] == polska["citiesStats"]
    assert (
        sum(c["activeOffersCount"] for c in polska["citiesStats"])
        == (polska["filteredStats"]["totalSales"])
    )


def test_each_city_sums_up_its_investments() -> None:
    """On the country's page: ``investmentCount``, ``activeOffersCount``, ``avgPrice`` (the
    mean of the city's active offers) and ``avgPricePerM2`` (weighted as above)."""
    data, sale = developer_props(DEVELOPER_POLSKA)

    for city in data["citiesStats"]:
        mine = [i for i in data["investments"] if i["city_slug"] == city["citySlug"]]
        active = active_sales(sale, {i["slug"] for i in mine})
        weighted = sum(i["avg_price_sqm"] * i["active_offers"] for i in mine)
        assert city["investmentCount"] == len(mine)
        assert city["activeOffersCount"] == sum(i["active_offers"] for i in mine) == len(active)
        assert city["avgPrice"] == round(mean([float(s["amount"]) for s in active]))
        assert city["avgPricePerM2"] == round(weighted / city["activeOffersCount"])


def test_the_city_of_the_page_is_its_filtered_stats() -> None:
    data, _ = developer_props(DEVELOPER_WARSZAWA)
    stats = data["filteredStats"]

    (row,) = [c for c in data["citiesStats"] if c["citySlug"] == "warszawa"]
    assert (row["investmentCount"], row["activeOffersCount"]) == (
        stats["totalProjects"],
        stats["totalSales"],
    )
    assert (row["avgPrice"], row["avgPricePerM2"]) == (
        stats["averagePrice"],
        stats["avgAmountPerM2"],
    )


def test_the_price_change_counts_do_not_match_their_sums_so_they_are_not_read() -> None:
    """The counts are 0 while the sums are not: their meaning is unclear (not shown)."""
    data, _ = developer_props(DEVELOPER_POLSKA)
    stats = data["filteredStats"]

    assert (stats["priceIncreaseCount"], stats["priceDecreaseCount"]) == (0, 0)
    assert stats["priceIncreaseSum"] != 0 and stats["priceDecreaseSum"] != 0
    assert not {"priceIncreaseCount", "priceIncreaseSum"} & set(
        developer_page_dto.DeveloperFilteredStatsDto.model_fields
    )
