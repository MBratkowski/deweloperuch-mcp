"""Tests of ``deweloperuch_mcp.usecases.get_investment``."""

import pytest

from deweloperuch_mcp.models.errors import (
    SERVICE_CHANGED,
    NotFoundError,
    ServiceError,
    UnexpectedResponseError,
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

    assert fake.calls == ["investment smolna", "price_events_of_offers smolna"]
    assert [o.history.events for o in found.listing.offers] == [EVENTS, (), ()]


def test_an_investment_gone_by_its_histories_is_not_found_without_a_way_around() -> None:
    """Only a second read the cache did not serve gets here: the investment is unknown by
    then, so a call without the history would not find it either (no hint)."""
    fake = FakeCatalogs(errors={"price_events_of_offers smolna": NotFoundError("Nie ma.")})

    with pytest.raises(NotFoundError) as caught:
        GetInvestment(fake, EchoPageLinks()).execute(
            GetInvestmentRequest(investment_slug=InvestmentSlug("smolna"), include_history=True)
        )

    assert str(caught.value) == "Historia cen inwestycji 'smolna': Nie ma."


def test_histories_off_the_contract_say_what_to_do_instead() -> None:
    """D12, D21: the investment read, only its offers' histories did not. The message keeps
    what happened and adds what to call instead (the investment without its histories, one
    offer's history); the error's type, pause and detail stay."""
    failure = UnexpectedResponseError(
        f"Dane z serwisu nie pasują do kontraktu klienta (inny format). {SERVICE_CHANGED}",
        5.0,
        detail="sale.0.ev: Field required",
    )
    fake = FakeCatalogs(errors={"price_events_of_offers smolna": failure})

    with pytest.raises(UnexpectedResponseError) as caught:
        GetInvestment(fake, EchoPageLinks()).execute(
            GetInvestmentRequest(investment_slug=InvestmentSlug("smolna"), include_history=True)
        )

    assert str(caught.value) == (
        "Historia cen inwestycji 'smolna': Dane z serwisu nie pasują do kontraktu klienta "
        "(inny format). Serwis mógł się zmienić po aktualizacji. Nie ponawiaj tego wywołania: "
        "zgłoś to użytkownikowi. Zamiast tego możesz pobrać inwestycję bez include_history "
        "albo historię jednej oferty przez get_offer."
    )
    assert (caught.value.pause_seconds, caught.value.detail) == (5.0, failure.detail)


def test_histories_that_miss_an_offer_fail_closed() -> None:
    """Events of another state of the investment (an answer the cache could not keep, read
    twice): an offer kept without its entry gets no made-up empty history."""
    fake = FakeCatalogs(histories={1: (), 2: EVENTS})

    with pytest.raises(UnexpectedResponseError) as caught:
        GetInvestment(fake, EchoPageLinks()).execute(
            GetInvestmentRequest(investment_slug=InvestmentSlug("smolna"), include_history=True)
        )

    assert str(caught.value) == (
        "Historia cen inwestycji 'smolna': dane z serwisu nie mają historii części ofert. "
        "Serwis mógł się zmienić po aktualizacji. Nie ponawiaj tego wywołania: zgłoś to "
        "użytkownikowi. Zamiast tego możesz pobrać inwestycję bez include_history albo "
        "historię jednej oferty przez get_offer."
    )
    assert caught.value.detail == "brak historii ofert 3"


def test_an_investment_off_the_contract_points_to_nothing_else() -> None:
    """Without the investment there is no history either: its own message, no hint."""
    fake = FakeCatalogs(errors={"investment smolna": UnexpectedResponseError("inny format")})

    with pytest.raises(UnexpectedResponseError) as caught:
        GetInvestment(fake, EchoPageLinks()).execute(
            GetInvestmentRequest(investment_slug=InvestmentSlug("smolna"), include_history=True)
        )

    assert str(caught.value) == "Inwestycja 'smolna': inny format"
    assert fake.calls == ["investment smolna"]


def test_other_service_errors_of_the_histories_keep_their_message() -> None:
    fake = FakeCatalogs(
        errors={"price_events_of_offers smolna": ServiceError("Serwis odpowiedział błędem.", 10)}
    )

    with pytest.raises(ServiceError) as caught:
        GetInvestment(fake, EchoPageLinks()).execute(
            GetInvestmentRequest(investment_slug=InvestmentSlug("smolna"), include_history=True)
        )

    assert type(caught.value) is ServiceError
    assert str(caught.value) == "Historia cen inwestycji 'smolna': Serwis odpowiedział błędem."
    assert caught.value.pause_seconds == 10


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
