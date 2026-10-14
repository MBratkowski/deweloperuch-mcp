"""Tests of ``deweloperuch_mcp.usecases.get_offer``."""

import pytest

from deweloperuch_mcp.models.errors import (
    NotFoundError,
)
from deweloperuch_mcp.models.values import (
    InvestmentSlug,
    OfferId,
)
from deweloperuch_mcp.usecases.get_offer import GetOffer, GetOfferRequest
from support.fakes.catalogs import (
    EVENTS,
    INVESTMENT,
    EchoPageLinks,
    FakeCatalogs,
)
from support.fakes.clocks import CLOCK


def test_an_offer_comes_with_its_history_and_links() -> None:
    fake = FakeCatalogs()

    found = GetOffer(fake, fake, EchoPageLinks(), CLOCK).execute(
        GetOfferRequest(offer_id=OfferId(2), investment_slug=InvestmentSlug("smolna"))
    )

    assert fake.calls == ["investment smolna", "price_events 2"]
    assert found.detail.offer.offer_id == 2
    assert found.detail.offer.history.events == EVENTS
    assert found.detail.investment is INVESTMENT
    assert (found.investment_url, found.developer_url) == ("investment:smolna", "developer:atal")
    # As of the clock's day: 1.0 (2025-02-25) in effect when the window began, then the
    # return at 2.0 (2026-10-03).
    assert found.price_flags is not None
    assert (found.price_flags.lowest_price_30d, found.price_flags.price_changes) == (1.0, 1)


def test_an_offer_outside_its_investment_is_not_found_without_asking_for_events() -> None:
    fake = FakeCatalogs()

    with pytest.raises(NotFoundError) as caught:
        GetOffer(fake, fake, EchoPageLinks(), CLOCK).execute(
            GetOfferRequest(offer_id=OfferId(999), investment_slug=InvestmentSlug("smolna"))
        )

    assert str(caught.value) == (
        "Inwestycja 'smolna' nie ma oferty 999. Sprawdź offer_id i investment_slug (oba podaje "
        "search_offers); wszystkie oferty inwestycji zwraca get_investment."
    )
    assert fake.calls == ["investment smolna"]


def test_an_unknown_investment_says_where_slugs_come_from() -> None:
    fake = FakeCatalogs(errors={"investment smolna": NotFoundError("404")})

    with pytest.raises(NotFoundError) as caught:
        GetOffer(fake, fake, EchoPageLinks(), CLOCK).execute(
            GetOfferRequest(offer_id=OfferId(2), investment_slug=InvestmentSlug("smolna"))
        )

    assert str(caught.value) == (
        "Nie znaleziono inwestycji 'smolna'. Slug inwestycji podaje search_investments, "
        "search_offers albo get_developer (pole investment_slug)."
    )


def test_an_offer_without_history_is_explained() -> None:
    fake = FakeCatalogs(errors={"price_events 2": NotFoundError("404")})

    with pytest.raises(NotFoundError, match="^Serwis nie ma historii ceny oferty 2 z inwestycji"):
        GetOffer(fake, fake, EchoPageLinks(), CLOCK).execute(
            GetOfferRequest(offer_id=OfferId(2), investment_slug=InvestmentSlug("smolna"))
        )
