"""Contract of ``deweloperuch_mcp.api.dto.gov_map_stats_dto`` with the service's real
answers: the capture of 2026-11-02 (tests/fixtures/api/gov_map_stats_20261102.json), and
what its values are, against the government statistics pages of two cities
(tests/fixtures/rsc/stats_gov_warszawa_20261031.rsc, stats_gov_wroclaw_20261030.rsc).

These comparisons are the evidence behind the descriptions of ``indicator`` in
``rank_locations`` (spec check of 2026-11-02): each value is the page's value for the
period of ``asOf``, or for the dwellings the sum of the 12 months ending in it; the area
matches no series of the page.
"""

from pathlib import Path

import pytest

from deweloperuch_mcp.api.adapters.city_indicators_api import CITY_INDICATORS
from deweloperuch_mcp.api.dto.dto import Dto
from deweloperuch_mcp.api.dto.gov_map_stats_dto import GovMapStatsDto
from deweloperuch_mcp.api.dto.government_stats_page_dto import GovernmentStatsPageDto
from deweloperuch_mcp.api.dto.place_names_dto import PlaceNamesDto
from deweloperuch_mcp.models.government_statistics import Dataset, LocationStatistics
from deweloperuch_mcp.models.indicator_ranking import Indicator
from deweloperuch_mcp.models.values import LocationSlug
from support.providers.routes.rankings import INDICATORS_2026_11_02, captured
from support.providers.rsc import STATS_GOV_WARSZAWA_20261031, STATS_GOV_WROCLAW_20261030, raw

PAGES = {"warszawa": STATS_GOV_WARSZAWA_20261031, "wroclaw": STATS_GOV_WROCLAW_20261030}


def capture() -> GovMapStatsDto:
    return Dto.validated(GovMapStatsDto, captured(INDICATORS_2026_11_02), CITY_INDICATORS)


def value(city: str, indicator: Indicator) -> float | None:
    names = PlaceNamesDto.packaged().to_model()
    values = capture().to_model(indicator, names, path=CITY_INDICATORS)
    return next(found.value for found in values.cities if found.city_slug == city)


def page(city: str, dataset: Dataset) -> LocationStatistics:
    location = LocationSlug.parse(city)
    path = f"/statystyki/{city}/dane-rzadowe"
    found = GovernmentStatsPageDto.from_payload(raw(PAGES[city]), path=path, location=location)
    return found.to_model(location, dataset, path=path)


def series(city: str, dataset: Dataset, series_id: str) -> dict[str, float | None]:
    table = page(city, dataset).tables[dataset]
    found = next(item for item in table.series if item.series_id == series_id)
    return {point.period: point.value for point in found.points}


def test_66_cities_7_periods_and_nbp_prices_for_17() -> None:
    answer = capture()

    assert (
        captured(INDICATORS_2026_11_02)["asOf"]
        == answer.asOf.model_dump()
        == {
            "bezrobocie": "08.2026",
            "wynagrodzenie": "2025",
            "oddane": "08.2026",
            "rozpoczete": "08.2026",
            "powierzchnia": "08.2026",
            "przyrost": "2025",
            "nbpCena": "Q2 2026",
        }
    )
    assert len(answer.rows) == len({row.slug for row in answer.rows}) == 66
    assert sum(row.values.nbpCena is not None for row in answer.rows) == 17
    for key in ("bezrobocie", "wynagrodzenie", "oddane", "rozpoczete", "powierzchnia"):
        assert all(getattr(row.values, key) is not None for row in answer.rows), key
    every_key = {key for row in captured(INDICATORS_2026_11_02)["rows"] for key in row["values"]}
    assert every_key == set(answer.asOf.model_dump())


@pytest.mark.parametrize("city", list(PAGES))
@pytest.mark.parametrize(
    ("indicator", "dataset", "series_id", "period"),
    [
        (Indicator.UNEMPLOYMENT_RATE, Dataset.UNEMPLOYMENT, "rate", "2026-08"),
        (Indicator.AVERAGE_WAGE, Dataset.WAGES, "gross", "2025"),
        (Indicator.NATURAL_INCREASE, Dataset.DEMOGRAPHY, "natural_increase", "2025"),
        (Indicator.NBP_PRICE_PER_M2, Dataset.NBP_PRICES, "secondary_transaction", "2026-Q2"),
    ],
)
def test_a_value_is_the_pages_value_for_its_period(
    city: str, indicator: Indicator, dataset: Dataset, series_id: str, period: str
) -> None:
    """[P 2026-11-02]: the month of the unemployment rate, the year of the gross wage and of
    the natural increase, the quarter of the NBP transaction price of the secondary market."""
    assert value(city, indicator) == series(city, dataset, series_id)[period]


@pytest.mark.parametrize("city", list(PAGES))
@pytest.mark.parametrize(
    ("indicator", "series_id"),
    [
        (Indicator.DWELLINGS_COMPLETED, "completed_total"),
        (Indicator.DWELLINGS_STARTED, "started_total"),
    ],
)
def test_dwellings_are_the_sum_of_the_12_months_to_the_period(
    city: str, indicator: Indicator, series_id: str
) -> None:
    """[P 2026-11-02]: 2025-09..2026-08 summed (Warszawa completed 19,058, started 15,150;
    Wrocław 7,149 and 5,109); the page's chart of the same says „suma 12 miesięcy”."""
    months = series(city, Dataset.DWELLINGS_MONTHLY, series_id)
    window = list(months)[list(months).index("2026-08") - 11 :][:12]

    assert (window[0], window[-1]) == ("2025-09", "2026-08")
    assert value(city, indicator) == sum(months[month] or 0 for month in window)
    assert value(city, indicator) != months["2026-08"]
    assert "suma 12 miesięcy".encode() in raw(PAGES[city])


@pytest.mark.parametrize("city", list(PAGES))
def test_the_area_matches_no_series_of_the_page(city: str) -> None:
    """Warszawa 56.78 against 56.7 (2025) and 56.5 (2026); Wrocław 63.64 against 59.6 and
    66.6: "podana przez serwis", never "the average area of the year"."""
    area = value(city, Indicator.AVERAGE_DWELLING_AREA)
    yearly = series(city, Dataset.AVERAGE_AREA, "average_area")

    assert area is not None
    assert all(abs(area - (found or 0)) > 0.05 for found in yearly.values())


def test_the_pages_are_of_the_cities_compared() -> None:
    for city, path in PAGES.items():
        assert city in Path(path).name
