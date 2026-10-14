"""The session of the consumers end to end below them: errors in domain terms, what every
request carries. The real use cases and adapters; the service mocked (respx)."""

import httpx
import pytest
import respx

from deweloperuch_mcp import bootstrap, identity
from deweloperuch_mcp.errors import NotFoundError, ServiceError, UnexpectedResponseError
from support.providers import operations
from support.providers.routes.government_statistics import stats_routes
from support.providers.routes.investments import (
    INVESTMENT,
    INVESTMENT_EVENTS,
    SALE_EVENTS,
    investment_routes,
)
from support.providers.routes.locations import location_routes
from support.providers.routes.offers import sample_offers_route
from support.providers.samples import body, request_target


def test_an_offer_without_history_is_not_found_in_domain_terms(
    session: bootstrap.Session, service: respx.MockRouter
) -> None:
    service.get(INVESTMENT).respond(200, json=body("api.map_inv_visible"))
    service.get(SALE_EVENTS).respond(404)

    with pytest.raises(NotFoundError) as caught:
        operations.get_offer(session, 2377, "smolna")

    assert str(caught.value).startswith(
        "Serwis nie ma historii ceny oferty 2377 z inwestycji 'smolna'."
    )
    assert caught.value.detail == request_target("api.sale_events")


def test_an_investment_without_history_is_not_found_in_domain_terms(
    session: bootstrap.Session, service: respx.MockRouter
) -> None:
    service.get(INVESTMENT).respond(200, json=body("api.map_inv_visible"))
    service.get(INVESTMENT_EVENTS).respond(404)

    with pytest.raises(NotFoundError, match="get_offer") as caught:
        operations.get_investment(session, "smolna", include_history=True)

    assert "/api/" not in str(caught.value)
    assert caught.value.detail == request_target("api.inv_sale_events")


def test_service_errors_name_what_failed_and_keep_type_pause_and_detail(
    session: bootstrap.Session, service: respx.MockRouter
) -> None:
    service.route(method="GET", path__startswith="/ceny-ofertowe/").respond(
        503, headers={"Retry-After": "10"}, text="busy"
    )

    with pytest.raises(ServiceError) as caught:
        operations.search_offers(session, "warszawa")

    assert type(caught.value) is ServiceError
    assert str(caught.value).startswith(
        "Wyszukiwanie ofert w 'warszawa': Serwis odpowiedział błędem HTTP 503."
    )
    assert caught.value.pause_seconds == 10
    assert caught.value.detail is not None and caught.value.detail.endswith(": busy")
    assert "/ceny-ofertowe" not in str(caught.value) and "busy" not in str(caught.value)


def test_data_off_the_contract_names_the_investment(
    session: bootstrap.Session, service: respx.MockRouter
) -> None:
    service.get(INVESTMENT).respond(200, json={"unexpected": True})

    with pytest.raises(UnexpectedResponseError) as caught:
        operations.get_investment(session, "smolna")

    assert str(caught.value).startswith("Inwestycja 'smolna': Dane z serwisu nie pasują")
    assert caught.value.detail is not None
    assert caught.value.detail.startswith("/api/map/investments/visible/smolna: ")


def test_location_errors_name_the_search(
    session: bootstrap.Session, service: respx.MockRouter
) -> None:
    service.get(path="/api/cities").respond(500)

    with pytest.raises(ServiceError, match="^Wyszukiwanie miast: Serwis odpowiedział błędem"):
        operations.search_locations(session, "krak")


def test_every_request_of_every_service_sends_the_shared_user_agent(
    session: bootstrap.Session, service: respx.MockRouter
) -> None:
    location_routes(service)
    sample_offers_route(service)
    investment_routes(service)
    stats_routes(service)

    operations.search_locations(session, "krak")
    operations.search_offers(session, "warszawa")
    operations.get_investment(session, "smolna", include_history=True)
    operations.get_offer(session, 2377, "smolna")
    operations.get_government_statistics(session, "warszawa", "wages")

    requests: list[httpx.Request] = [call.request for call in service.calls]
    assert len(requests) == 7  # the investment of get_offer comes from the cache
    assert all(r.headers.get_list("user-agent") == [identity.USER_AGENT] for r in requests)
    assert all(r.method == "GET" for r in requests)
