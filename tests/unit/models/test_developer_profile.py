"""Tests of ``deweloperuch_mcp.models.developer_profile``."""

from deweloperuch_mcp.models.developer_profile import (
    DeveloperCity,
    DeveloperInvestment,
    DeveloperProfile,
    DeveloperSummary,
)
from deweloperuch_mcp.models.offer import DeveloperRef
from deweloperuch_mcp.models.values import CitySlug, InvestmentsLimit

ATAL = DeveloperRef(developer_slug="atal", name="ATAL S.A.")


def project(
    slug: str,
    active: int | None,
    *,
    city: str | None = "Kraków",
    city_slug: str | None = "krakow",
    price: float | None = None,
    area: float | None = None,
    per_m2: float | None = None,
) -> DeveloperInvestment:
    return DeveloperInvestment(
        investment_slug=slug,
        name=slug.upper(),
        city=city,
        city_slug=city_slug,
        status="active",
        active_offers=active,
        total_offers=None,
        avg_price=price,
        avg_area_m2=area,
        avg_price_per_m2=per_m2,
        developer=ATAL,
    )


def profile(*projects: DeveloperInvestment) -> DeveloperProfile:
    return DeveloperProfile(
        developer=ATAL, city=CitySlug("polska"), investments=projects, cities=()
    )


def place(slug: str, active: int | None, per_m2: float | None) -> DeveloperCity:
    return DeveloperCity(
        city=slug.upper(),
        city_slug=slug,
        investments=1,
        active_offers=active,
        avg_price_per_m2=per_m2,
    )


def in_cities(*cities: DeveloperCity) -> DeveloperProfile:
    return DeveloperProfile(developer=ATAL, city=CitySlug("polska"), investments=(), cities=cities)


# The four investments of ATAL in Warsaw on 2026-10-31 (active offers and their averages,
# tests/fixtures/rsc/developer_atal_warszawa_20261031.rsc).
WARSZAWA = (
    project("nowy-targowek-vi", 21, price=1073611.14, area=60.84, per_m2=17646),
    project("osiedle-poematu-ii", 5, price=881659.6, area=72.21, per_m2=12210),
    project("warszawska-58a", 32, price=966208.84, area=59.93, per_m2=16123),
    project("zakatek-harmonia-ii", 2, price=865126, area=90.73, per_m2=9536),
)


def test_investments_with_the_most_active_offers_first_unknown_last_ties_in_order() -> None:
    found = profile(project("a", 5), project("b", None), project("c", 9), project("d", 5))

    listing = found.listing(InvestmentsLimit(3))

    assert [item.investment_slug for item in listing.investments] == ["c", "a", "d"]
    assert listing.omitted == 1
    assert found.listing(InvestmentsLimit(10)).investments[-1].investment_slug == "b"


def test_a_listing_shows_every_city_the_most_active_offers_first() -> None:
    """Ties: the higher price per m² first; unknown figures last. The service's order (its
    chart lists the cities by price) does not matter."""
    cities = (
        place("a", 5, 10_000.0),
        place("b", None, 20_000.0),
        place("c", 9, 9_000.0),
        place("d", 5, 12_000.0),
        place("e", 5, None),
    )
    expected = ["c", "d", "a", "e", "b"]

    assert [c.city_slug for c in in_cities(*cities).listing(InvestmentsLimit(1)).cities] == expected
    shuffled = in_cities(*cities[2:], *cities[:2]).listing(InvestmentsLimit(1))
    assert [c.city_slug for c in shuffled.cities] == expected


def test_cities_that_tie_on_every_figure_keep_the_profiles_order() -> None:
    first, second = place("a", 5, 10_000.0), place("b", 5, 10_000.0)

    assert in_cities(first, second).listing(InvestmentsLimit(1)).cities == (first, second)
    assert in_cities(second, first).listing(InvestmentsLimit(1)).cities == (second, first)


def test_cities_from_investments_are_all_of_them_only_in_the_whole_country() -> None:
    """Without the service's list of cities, a city's profile knows only that city."""

    def scoped(city: str, from_investments: bool) -> DeveloperProfile:
        return DeveloperProfile(
            developer=ATAL,
            city=CitySlug(city),
            investments=(),
            cities=(),
            cities_from_investments=from_investments,
        )

    assert scoped("warszawa", True).cities_in_scope_only is True
    assert scoped("polska", True).cities_in_scope_only is False
    assert scoped("warszawa", False).cities_in_scope_only is False
    assert profile().cities_from_investments is False


def test_the_cities_of_investments_sum_them_up() -> None:
    """Each city of the investments counted as the summary counts, in the order of its
    first investment; a city without a name is named by its slug, investments without a
    city are left out."""
    cities = DeveloperCity.of_investments(
        (
            project("a", 2, city="Kraków", city_slug="krakow", per_m2=10_000.0),
            project("b", 1, city="Gdańsk", city_slug="gdansk", per_m2=13_000.0),
            project("c", 3, city="Kraków", city_slug="krakow", per_m2=12_000.0),
            project("d", 4, city=None, city_slug="reda", per_m2=9_000.0),
            project("e", 5, city=None, city_slug=None, per_m2=8_000.0),
        )
    )

    assert cities == (
        DeveloperCity(
            city="Kraków",
            city_slug="krakow",
            investments=2,
            active_offers=5,
            avg_price_per_m2=11_200.0,
        ),
        DeveloperCity(
            city="Gdańsk",
            city_slug="gdansk",
            investments=1,
            active_offers=1,
            avg_price_per_m2=13_000.0,
        ),
        DeveloperCity(
            city="reda", city_slug="reda", investments=1, active_offers=4, avg_price_per_m2=9_000.0
        ),
    )


def test_an_investment_knows_its_page() -> None:
    ref = project("a", 1).ref

    assert (ref.investment_slug, ref.city_slug, ref.developer.developer_slug) == (
        "a",
        "krakow",
        "atal",
    )


def test_the_summary_sums_up_the_investments_and_weighs_their_averages_by_active_offers() -> None:
    """The mean price and area of every active offer, and the price per m² as the service
    counts a city's (16,110.4, shown as 16,110: the Warsaw row of its chart of cities)."""
    summary = profile(*WARSZAWA).summary

    assert summary == DeveloperSummary(
        investments=4,
        active_offers=60,
        cities=1,
        avg_price=993384.0,
        avg_area_m2=62.3,
        avg_price_per_m2=16110.0,
    )


def test_the_summary_counts_each_city_once() -> None:
    summary = profile(
        project("a", 1, city_slug="krakow"),
        project("b", 2, city_slug="gdansk"),
        project("c", 3, city_slug="krakow"),
        project("d", 4, city_slug=None),
    ).summary

    assert (summary.investments, summary.active_offers, summary.cities) == (4, 10, 2)


def test_a_profile_without_investments_sums_up_to_nothing() -> None:
    assert profile().summary == DeveloperSummary(
        investments=0,
        active_offers=0,
        cities=0,
        avg_price=None,
        avg_area_m2=None,
        avg_price_per_m2=None,
    )


def test_an_average_some_investment_with_active_offers_lacks_is_unknown() -> None:
    """Weighing only the others would not be the mean of every active offer."""
    summary = profile(
        project("a", 2, price=500_000.0, area=50.0, per_m2=10_000.0),
        project("b", 1, price=None, area=40.0, per_m2=12_000.0),
    ).summary

    assert summary.avg_price is None
    assert (summary.avg_area_m2, summary.avg_price_per_m2) == (46.67, 10667.0)


def test_investments_without_active_offers_weigh_nothing() -> None:
    summary = profile(
        project("a", 2, price=500_000.0, area=50.0, per_m2=10_000.0),
        project("b", 0),
    ).summary

    assert (summary.active_offers, summary.avg_price, summary.avg_price_per_m2) == (
        2,
        500_000.0,
        10_000.0,
    )


def test_an_unknown_count_of_active_offers_makes_the_totals_unknown() -> None:
    summary = profile(project("a", 2, price=1.0, area=1.0, per_m2=1.0), project("b", None)).summary

    assert (summary.investments, summary.cities) == (2, 1)
    assert (summary.active_offers, summary.avg_price, summary.avg_area_m2) == (None, None, None)
    assert summary.avg_price_per_m2 is None
