"""Tests of ``deweloperuch_mcp.models.developer_profile``."""

from deweloperuch_mcp.models.developer_profile import (
    DeveloperInvestment,
    DeveloperProfile,
    DeveloperSummary,
)
from deweloperuch_mcp.models.offer import DeveloperRef
from deweloperuch_mcp.models.values import CitySlug, InvestmentsLimit

ATAL = DeveloperRef(developer_slug="atal", name="ATAL S.A.")


def project(slug: str, active: int | None) -> DeveloperInvestment:
    return DeveloperInvestment(
        investment_slug=slug,
        name=slug.upper(),
        city="Kraków",
        city_slug="krakow",
        status="active",
        active_offers=active,
        total_offers=None,
        avg_price=None,
        avg_area_m2=None,
        avg_price_per_m2=None,
        developer=ATAL,
    )


def profile(*projects: DeveloperInvestment) -> DeveloperProfile:
    return DeveloperProfile(
        developer=ATAL,
        city=CitySlug("polska"),
        summary=DeveloperSummary(
            investments=len(projects),
            active_offers=None,
            cities=None,
            avg_price=None,
            avg_area_m2=None,
            avg_price_per_m2=None,
        ),
        investments=projects,
        cities=(),
    )


def test_investments_with_the_most_active_offers_first_unknown_last_ties_in_order() -> None:
    found = profile(project("a", 5), project("b", None), project("c", 9), project("d", 5))

    listing = found.listing(InvestmentsLimit(3))

    assert [item.investment_slug for item in listing.investments] == ["c", "a", "d"]
    assert listing.omitted == 1
    assert found.listing(InvestmentsLimit(10)).investments[-1].investment_slug == "b"


def test_an_investment_knows_its_page() -> None:
    ref = project("a", 1).ref

    assert (ref.investment_slug, ref.city_slug, ref.developer.developer_slug) == (
        "a",
        "krakow",
        "atal",
    )
