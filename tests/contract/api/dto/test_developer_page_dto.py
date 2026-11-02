"""Contract of ``deweloperuch_mcp.api.dto.developer_page_dto`` with the service's real
answers: the 2.0 developer pages of 2026-10-31 (tests/fixtures/rsc/developer_*_20261031.rsc,
the sample ``page.developer.v2_spec``) and, for the meaning of an investment's figures, the
offer snapshot of Warsaw of the same day (tests/fixtures/api/offer_snapshot_warszawa_20261031.json).

[P 2026-10-31] docs/discovery/pages-rsc.md, the developer page: the developer and its
investments are props of the element held by the prop ``hero``; the cities are the rows of
the ``spec`` prop ``ceny-w-miastach``, which the page of a developer in one city lacks; the
totals of 1.0 (``filteredStats``, ``citiesStats``) are gone, so the summary is computed
(``DeveloperSummary.of``).
"""

import dataclasses
import json
from pathlib import Path
from statistics import mean
from typing import Any

import pytest

from deweloperuch_mcp.api.dto.developer_page_dto import (
    CITIES_CHART,
    CitiesChartDto,
    DeveloperPageDto,
)
from deweloperuch_mcp.errors import NotFoundError
from deweloperuch_mcp.flight import NOT_FOUND_DIGEST, component_props, error_digests
from deweloperuch_mcp.models.developer_profile import (
    DeveloperCity,
    DeveloperInvestment,
    DeveloperProfile,
    DeveloperSummary,
)
from deweloperuch_mcp.models.offer import DeveloperRef
from deweloperuch_mcp.models.values import CitySlug
from support.providers.rsc import (
    API_FIXTURES,
    DEVELOPER_CERES_WARSZAWA_20261031,
    DEVELOPER_DOM_DEVELOPMENT_WARSZAWA_20261031,
    DEVELOPER_POLSKA_20261031,
    DEVELOPER_UNKNOWN_CITY_20261102,
    DEVELOPER_UNKNOWN_POLSKA_20261031,
    DEVELOPER_WARSZAWA_20261031,
    UNKNOWN_CITY,
    UNKNOWN_DEVELOPER,
    raw,
)
from support.providers.samples import body

PROFILES = {"warszawa": DEVELOPER_WARSZAWA_20261031, "polska": DEVELOPER_POLSKA_20261031}
SNAPSHOT_WARSZAWA = API_FIXTURES / "offer_snapshot_warszawa_20261031.json"
"""Every active offer of Warsaw on 2026-10-31, rows ``[sale_id, invest_id, 0, amount,
price per m², size, change]`` (docs/discovery/endpoints.md, ``map/offer-snapshot``)."""
FIGURES = ("active_offers", "total_offers", "avg_amount", "avg_size", "avg_price_sqm")
"""The figures of an investment the DTO reads."""


def page(city: str) -> DeveloperPageDto:
    return page_of(PROFILES[city], city, "atal")


def page_of(fixture: Path, city: str, developer: str) -> DeveloperPageDto:
    path = f"/ceny-ofertowe/{city}/deweloperzy/{developer}"
    return DeveloperPageDto.from_payload(raw(fixture), path=path)


def profile_of(city: str) -> DeveloperProfile:
    return page(city).to_model(CitySlug(city))


def props(city: str) -> list[tuple[str, Any]]:
    return list(component_props(raw(PROFILES[city])))


def investment_rows(city: str) -> list[dict[str, Any]]:
    """The hero's ``investments``: the first value of the prop that is a list."""
    return next(v for n, v in props(city) if n == "investments" and isinstance(v, list))


def in_one_city(profile: DeveloperProfile, city_slug: str) -> DeveloperProfile:
    """``profile`` with only the investments in ``city_slug``."""
    mine = tuple(item for item in profile.investments if item.city_slug == city_slug)
    return dataclasses.replace(profile, investments=mine)


def chart_rows(city: str) -> list[dict[str, Any]]:
    chart = next(
        value
        for name, value in props(city)
        if name == "spec" and isinstance(value, dict) and value.get("id") == CITIES_CHART
    )
    rows: list[dict[str, Any]] = chart["views"][""]["rows"]
    return rows


@pytest.mark.parametrize("city", PROFILES)
def test_the_developer_page_parses(city: str) -> None:
    parsed = page(city)

    assert (parsed.developerSlug, parsed.developerName) == ("atal", "ATAL S.A.")
    assert len(parsed.investments) == {"warszawa": 4, "polska": 42}[city]
    assert parsed.cities is not None and len(parsed.cities.views.default.rows) == 14


def test_the_developer_is_named_by_the_hero_element_alone() -> None:
    """``developer`` is null: the page has no website or description of the developer."""
    found = props("warszawa")
    hero = next(value for name, value in found if name == "hero")

    assert ("developer", None) in found
    assert {"investments", "developerSlug", "developerName"} <= set(hero[3])
    assert not {"website", "description"} & set(hero[3])


@pytest.mark.parametrize("city", PROFILES)
def test_every_investment_has_the_fields_read_and_its_figures_are_numbers(city: str) -> None:
    for row in investment_rows(city):
        assert {"slug", "name", "city", "city_slug", "status", *FIGURES} <= row.keys()
        assert all(isinstance(row[figure], int | float) for figure in FIGURES)
        assert row["status"] == "active" and 0 < row["active_offers"] <= row["total_offers"]


def test_the_figures_of_an_investment_are_those_of_its_active_offers() -> None:
    """[P 2026-10-31] against the offer snapshot of Warsaw of the same day, which holds
    active offers only: ``active_offers`` is the number of the investment's offers there,
    ``avg_amount`` and ``avg_size`` their mean price and area, ``avg_price_sqm`` their
    total price over their total area, rounded."""
    sales = json.loads(SNAPSHOT_WARSZAWA.read_bytes())["sales"]

    for row in investment_rows("warszawa"):
        mine = [sale for sale in sales if sale[1] == row["invest_id"]]
        amounts, sizes = [sale[3] for sale in mine], [sale[5] for sale in mine]
        assert row["active_offers"] == len(mine)
        assert row["avg_amount"] == pytest.approx(mean(amounts), abs=0.01)
        assert row["avg_size"] == pytest.approx(mean(sizes), abs=0.01)
        assert row["avg_price_sqm"] == round(sum(amounts) / sum(sizes))


def test_the_profile_of_warsaw() -> None:
    profile = profile_of("warszawa")

    assert profile.developer == DeveloperRef(developer_slug="atal", name="ATAL S.A.")
    assert profile.city == CitySlug("warszawa")
    assert profile.investments[0] == DeveloperInvestment(
        investment_slug="nowy-targowek-vi",
        name="Nowy Targówek VI",
        city="Warszawa",
        city_slug="warszawa",
        status="active",
        active_offers=21,
        total_offers=75,
        avg_price=1073611.14,
        avg_area_m2=60.84,
        avg_price_per_m2=17646.0,
        developer=profile.developer,
    )
    assert profile.summary == DeveloperSummary(
        investments=4,
        active_offers=60,
        cities=1,
        avg_price=993384.0,
        avg_area_m2=62.3,
        avg_price_per_m2=16110.0,
    )


def test_the_profile_of_the_whole_country_has_every_investment() -> None:
    """[P 2026-10-31] ``polska`` works on 2.0: 42 investments in 14 cities."""
    summary = profile_of("polska").summary

    assert (summary.investments, summary.active_offers, summary.cities) == (42, 3879, 14)
    assert summary.avg_price_per_m2 == 12425.0


def test_the_cities_chart_is_one_of_four_charts() -> None:
    """The page has four ``spec`` props; the DTO takes the one with the id, wherever it
    is (tests/unit/api/dto/test_developer_page_dto.py moves it)."""
    ids = [value["id"] for name, value in props("warszawa") if name == "spec"]

    assert ids == [CITIES_CHART, "rozklad-metrazy", "oferty-wg-metrazu", "tempo-sprzedazy-wykres"]


@pytest.mark.parametrize("city", PROFILES)
def test_the_counts_of_a_city_are_display_strings_of_digits(city: str) -> None:
    """Why the DTO parses them: the active offers (``extra``, the tip's ``oferty``) and the
    investments (the tip's ``inwestycje``) are strings; the price per m² is a number."""
    for row in chart_rows(city):
        tip = {item["key"]: item["value"] for item in row["tip"]["rows"]}
        assert isinstance(row["extra"], str) and row["extra"].isdigit()
        assert tip["oferty"] == row["extra"]
        assert isinstance(tip["inwestycje"], str) and tip["inwestycje"].isdigit()
        assert isinstance(row["value"], int)


def test_each_city_sums_up_its_investments() -> None:
    """[P 2026-10-31] on the country's page, each row of the chart sums up the investments
    of its city: ``extra`` their active offers, the tip's ``inwestycje`` their number,
    ``label`` their city, and ``value`` their price per m² weighted by their active offers,
    as ``DeveloperProfile.summary`` of those investments computes it.

    ``value`` and the summary differ by 1 PLN in one city of 14: the page rounds each
    investment's figure to whole PLN, the service weighs unrounded ones (Katowice: 12,596
    against 12,596.51, rounded to 12,597).
    """
    profile = profile_of("polska")
    rows = investment_rows("polska")
    off: list[str] = []

    assert {city.city_slug for city in profile.cities} == {row["city_slug"] for row in rows}
    for city in profile.cities:
        mine = [row for row in rows if row["city_slug"] == city.city_slug]
        summary = in_one_city(profile, city.city_slug).summary
        counts = (len(mine), sum(row["active_offers"] for row in mine))
        assert (city.investments, city.active_offers) == counts
        assert (summary.investments, summary.active_offers) == counts
        assert {row["city"] for row in mine} == {city.city}
        assert city.avg_price_per_m2 is not None and summary.avg_price_per_m2 is not None
        assert abs(city.avg_price_per_m2 - summary.avg_price_per_m2) <= 1
        if city.avg_price_per_m2 != summary.avg_price_per_m2:
            off.append(city.city_slug)
    assert off == ["katowice"]


def test_the_city_of_the_page_is_its_summary() -> None:
    """Warsaw's row of the chart is what ``DeveloperProfile.summary`` computes from the
    investments of Warsaw's page (16,110.4 against the chart's 16,110)."""
    profile = profile_of("warszawa")
    summary = profile.summary

    (row,) = [city for city in profile.cities if city.city_slug == "warszawa"]
    assert (row.investments, row.active_offers, row.avg_price_per_m2) == (4, 60, 16110.0)
    assert (summary.investments, summary.active_offers, summary.avg_price_per_m2) == (
        4,
        60,
        16110.0,
    )


def test_the_cities_are_every_city_of_the_developer_whatever_the_page() -> None:
    """The chart of Warsaw's page and the country's differ only in the row of the page's
    own city (``current``, without ``href``)."""

    def without_place(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [{k: v for k, v in row.items() if k not in {"current", "href"}} for row in rows]

    assert without_place(chart_rows("warszawa")) == without_place(chart_rows("polska"))
    assert [row["key"] for row in chart_rows("warszawa") if row["current"]] == ["warszawa"]
    assert profile_of("warszawa").cities == profile_of("polska").cities


def test_the_chart_lists_the_cities_by_their_price_per_m2_the_highest_first() -> None:
    """The service's order, which a result does not keep: ``DeveloperProfile.listing``
    shows the most active offers first."""
    prices = [city.avg_price_per_m2 or 0.0 for city in profile_of("polska").cities]

    assert 0.0 not in prices
    assert prices == sorted(prices, reverse=True)


def test_a_developer_in_one_city_has_no_chart_of_cities() -> None:
    """[P 2026-10-31] Ceres Development, one investment in Warsaw: the ``hero`` element's
    props, three of the four charts, no ``ceny-w-miastach``. Its one city comes from its
    investments ([W] for any page without the chart,
    tests/unit/api/dto/test_developer_page_dto.py)."""
    found = list(component_props(raw(DEVELOPER_CERES_WARSZAWA_20261031)))
    ids = [value["id"] for name, value in found if name == "spec"]

    parsed = page_of(DEVELOPER_CERES_WARSZAWA_20261031, "warszawa", "ceres-development")
    profile = parsed.to_model(CitySlug("warszawa"))

    assert sorted(ids) == ["oferty-wg-metrazu", "rozklad-metrazy", "tempo-sprzedazy-wykres"]
    assert parsed.cities is None
    assert (profile.developer.developer_slug, profile.developer.name) == (
        "ceres-development",
        "Ceres Development Sp. z o.o.",
    )
    assert profile.cities == (
        DeveloperCity(
            city="Warszawa",
            city_slug="warszawa",
            investments=1,
            active_offers=110,
            avg_price_per_m2=12996.0,
        ),
    )
    assert profile.summary == DeveloperSummary(
        investments=1,
        active_offers=110,
        cities=1,
        avg_price=662273.0,
        avg_area_m2=50.96,
        avg_price_per_m2=12996.0,
    )


def test_a_count_of_thousands_is_grouped_with_a_no_break_space() -> None:
    """[P 2026-10-31] Dom Development in Warsaw: ``extra`` and the tip's ``oferty`` read
    ``"1 816"`` with a no-break space (U+00A0): the active offers of the page's 28
    investments, which the summary counts too."""
    fixture = DEVELOPER_DOM_DEVELOPMENT_WARSZAWA_20261031
    chart = next(
        value
        for name, value in component_props(raw(fixture))
        if name == "spec" and isinstance(value, dict) and value.get("id") == CITIES_CHART
    )
    (row,) = [row for row in chart["views"][""]["rows"] if row["key"] == "warszawa"]
    tip = {item["key"]: item["value"] for item in row["tip"]["rows"]}

    profile = page_of(fixture, "warszawa", "dom-development").to_model(CitySlug("warszawa"))

    assert row["extra"] == tip["oferty"] == "1\u00a0816"
    assert [city.city_slug for city in profile.cities] == ["warszawa", "krakow", "wroclaw"]
    (warszawa,) = [city for city in profile.cities if city.city_slug == "warszawa"]
    summary = profile.summary
    assert (warszawa.investments, warszawa.active_offers, warszawa.avg_price_per_m2) == (
        28,
        1816,
        18568.0,
    )
    assert (summary.investments, summary.active_offers, summary.avg_price_per_m2) == (
        28,
        1816,
        18568.0,
    )


def test_an_unknown_developer_in_the_whole_country_is_not_found() -> None:
    """[P 2026-10-31] the page for Poland answers as a city's: a 200 with Next.js's 404
    marker."""
    with pytest.raises(NotFoundError) as caught:
        page_of(DEVELOPER_UNKNOWN_POLSKA_20261031, "polska", UNKNOWN_DEVELOPER)

    assert caught.value.detail is not None and NOT_FOUND_DIGEST in caught.value.detail


def test_developer_page_of_an_unknown_city_is_not_found() -> None:
    """T39 [P 2026-11-02]: ATAL in a city the service does not know. The page has no
    ``hero`` and no 404 marker; its one error row redirects to ATAL's page for the whole
    country. Its ``notFound`` prop is no marker: every page has one (the known
    developer's page too, the not-found boundary of the layout)."""
    payload = raw(DEVELOPER_UNKNOWN_CITY_20261102)
    country = "/ceny-ofertowe/polska/deweloperzy/atal"
    for page_payload in (payload, raw(DEVELOPER_WARSZAWA_20261031)):
        assert any(name == "notFound" for name, _ in component_props(page_payload))
    assert error_digests(payload) == [f"NEXT_REDIRECT;replace;{country};308;"]

    with pytest.raises(NotFoundError):
        DeveloperPageDto.from_payload(
            payload, path=f"/ceny-ofertowe/{UNKNOWN_CITY}/deweloperzy/atal", country=country
        )


def test_the_sample_of_the_cities_chart_parses() -> None:
    """``page.developer.v2_spec``: the chart with its rows cut to three."""
    chart = CitiesChartDto.model_validate(body("page.developer.v2_spec"))

    assert chart.to_model() == (
        DeveloperCity(
            city="Warszawa",
            city_slug="warszawa",
            investments=4,
            active_offers=60,
            avg_price_per_m2=16110.0,
        ),
        DeveloperCity(
            city="Gdańsk",
            city_slug="gdansk",
            investments=6,
            active_offers=251,
            avg_price_per_m2=14036.0,
        ),
        DeveloperCity(
            city="Kraków",
            city_slug="krakow",
            investments=7,
            active_offers=705,
            avg_price_per_m2=13757.0,
        ),
    )
