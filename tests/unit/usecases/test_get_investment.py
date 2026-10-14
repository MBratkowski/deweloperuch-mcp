"""Tests of ``deweloperuch_mcp.usecases.get_investment``."""

import pytest

from deweloperuch_mcp.models.errors import (
    NotFoundError,
)
from deweloperuch_mcp.models.government_statistics import Dataset
from deweloperuch_mcp.models.values import InvestmentSlug, OfferId, OffersLimit
from deweloperuch_mcp.usecases.get_government_statistics import (
    GetGovernmentStatisticsRequest,
)
from deweloperuch_mcp.usecases.get_investment import GetInvestment, GetInvestmentRequest
from deweloperuch_mcp.usecases.get_offer import GetOfferRequest
from deweloperuch_mcp.usecases.search_locations import SearchLocationsRequest
from support.fakes.catalogs import (
    EVENTS,
    EchoPageLinks,
    FakeCatalogs,
)


def test_an_investment_without_history_asks_once() -> None:
    fake = FakeCatalogs()

    found = GetInvestment(fake, EchoPageLinks()).execute(
        GetInvestmentRequest(investment_slug=InvestmentSlug("smolna"), limit=OffersLimit(2))
    )

    assert fake.calls == ["investment smolna"]
    assert [o.offer_id for o in found.listing.offers] == [2, 3]  # active first
    assert found.listing.omitted == 1
    assert all(o.history.events is None for o in found.listing.offers)
    assert (found.investment_url, found.developer_url) == ("investment:smolna", "developer:atal")


def test_an_investment_with_history_attaches_it_to_the_offers_kept() -> None:
    fake = FakeCatalogs()

    found = GetInvestment(fake, EchoPageLinks()).execute(
        GetInvestmentRequest(investment_slug=InvestmentSlug("smolna"), include_history=True)
    )

    assert fake.calls == ["investment smolna", "price_events_of_offers 33"]
    assert [o.history.events for o in found.listing.offers] == [EVENTS, (), ()]


def test_an_investment_without_histories_is_explained() -> None:
    fake = FakeCatalogs(errors={"price_events_of_offers 33": NotFoundError("404")})

    with pytest.raises(NotFoundError, match="get_offer"):
        GetInvestment(fake, EchoPageLinks()).execute(
            GetInvestmentRequest(investment_slug=InvestmentSlug("smolna"), include_history=True)
        )


def test_the_other_operations_arguments() -> None:
    assert SearchLocationsRequest.parse(query="  Kraków ").query.text == "Kraków"
    expected = GetOfferRequest(offer_id=OfferId(2377), investment_slug=InvestmentSlug("smolna"))
    assert GetOfferRequest.parse(offer_id=2377, investment_slug=" smolna ") == expected
    assert GetInvestmentRequest.parse(
        investment_slug="smolna", include_history=True, limit=2
    ) == GetInvestmentRequest(
        investment_slug=InvestmentSlug("smolna"), include_history=True, limit=OffersLimit(2)
    )
    found = GetGovernmentStatisticsRequest.parse(
        location=" Warszawa ", dataset=" wages ", periods=3
    )
    assert (found.location.value, found.dataset, found.periods.value) == (
        "warszawa",
        Dataset.WAGES,
        3,
    )
