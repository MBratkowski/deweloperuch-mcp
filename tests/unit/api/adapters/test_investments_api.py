"""Tests of ``deweloperuch_mcp.api.adapters.investments_api``."""

import datetime as dt
from typing import Any

import pytest
import respx

from deweloperuch_mcp import identity
from deweloperuch_mcp.api.adapters.investments_api import InvestmentsApi
from deweloperuch_mcp.api.adapters.locations_api import LocationsApi
from deweloperuch_mcp.api.adapters.offers_api import OffersApi
from deweloperuch_mcp.api.dto import investment_dto, sale_events_dto
from deweloperuch_mcp.api.dto.cities_dto import CitiesDto
from deweloperuch_mcp.api.dto.investment_price_events_dto import InvestmentPriceEventsDto
from deweloperuch_mcp.api.dto.location_search_dto import LocationSearchDto
from deweloperuch_mcp.api.http.transport import HttpClient
from deweloperuch_mcp.errors import InvalidInputError, UnexpectedResponseError
from deweloperuch_mcp.models.price_history import PriceEvent
from deweloperuch_mcp.models.values import InvestmentSlug
from support.providers.routes.investments import SMOLNA_2026_10_31
from support.providers.samples import body, request_target

SMOLNA = identity.BASE_URL + "/api/map/investments/visible/smolna"
"""The request of the 2.0 capture of ``smolna`` (tests/fixtures/api/README.md)."""


@pytest.mark.parametrize(
    ("sample", "call", "model"),
    [
        ("api.cities_q", lambda http: LocationsApi(http).city_search("krak", 8), CitiesDto),
        (
            "api.location_search",
            lambda http: LocationsApi(http).location_search("mokot", 6),
            LocationSearchDto,
        ),
        (
            "api.map_inv_visible",
            lambda http: InvestmentsApi(http).visible_investment("smolna"),
            investment_dto.InvestmentDto,
        ),
        (
            "api.map_inv_visible.no_v",
            lambda http: InvestmentsApi(http).visible_price_events("nowy-czechow"),
            InvestmentPriceEventsDto,
        ),
        (
            "api.sale_events",
            lambda http: OffersApi(http).sale_events(2377),
            sale_events_dto.SaleEventsDto,
        ),
    ],
)
def test_json_endpoint_requests_what_the_sample_requested(
    http: HttpClient, service: respx.MockRouter, sample: str, call: Any, model: type[Any]
) -> None:
    url = identity.BASE_URL + request_target(sample)
    route = service.get(url).respond(200, json=body(sample))

    parsed = call(http)

    assert parsed == model.model_validate(body(sample))
    request = route.calls.last.request
    assert str(request.url) == url
    assert request.headers.get_list("user-agent") == [identity.USER_AGENT]
    assert request.headers["accept"] == "application/json"


@pytest.mark.parametrize("slug", ["a/..?b", "..", "a b", "kraków"])
def test_slugs_with_separators_never_reach_the_service(
    http: HttpClient, service: respx.MockRouter, slug: str
) -> None:
    """Encoded, they cannot change the path; and the transport refuses encoded paths."""
    with pytest.raises(InvalidInputError):
        InvestmentsApi(http).visible_investment(slug)

    assert service.calls.call_count == 0


@pytest.mark.parametrize(
    ("content", "content_type", "message"),
    [
        (b"<!DOCTYPE html><html></html>", "text/html", "HTML"),
        (b"{not json", "application/json", "JSON"),
        (b'{"city": "Warszawa"}', "application/json", "kontrakt"),
    ],
)
def test_json_that_does_not_match_the_contract_is_unexpected(
    http: HttpClient, service: respx.MockRouter, content: bytes, content_type: str, message: str
) -> None:
    service.get(identity.BASE_URL + "/api/map/investments/visible/smolna").respond(
        200, content=content, headers={"Content-Type": content_type}
    )

    with pytest.raises(UnexpectedResponseError, match=message):
        InvestmentsApi(http).visible_investment("smolna")


def test_the_price_events_come_from_the_answer_of_the_investment(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """[P 2026-10-30] the service sends the offers' events with the investment (``ev``):
    reading them after the investment sends no request of its own, as the client's cache
    keeps the answer (D2)."""
    route = service.get(SMOLNA).respond(200, content=SMOLNA_2026_10_31.read_bytes())
    api = InvestmentsApi(http)

    investment = api.investment(InvestmentSlug("smolna"))
    events = api.price_events_of_offers(InvestmentSlug("smolna"))

    assert route.call_count == 1
    assert set(events) == {offer.offer_id for offer in investment.offers}
    assert events[206087] == (
        PriceEvent(date=dt.date(2026, 10, 3), kind="offer", price=1_679_796.0),
    )


def test_an_answer_the_cache_may_not_keep_is_read_again(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """``no-store`` (this route does not send it [P 2026-10-30]): the events cost a second
    request, and they are still read from the investment's answer."""
    route = service.get(SMOLNA).respond(
        200, content=SMOLNA_2026_10_31.read_bytes(), headers={"Cache-Control": "no-store"}
    )
    api = InvestmentsApi(http)

    api.investment(InvestmentSlug("smolna"))
    events = api.price_events_of_offers(InvestmentSlug("smolna"))

    assert route.call_count == 2
    assert len(events) == 17


def test_an_answer_without_events_is_off_the_contract_only_for_the_events(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """The answer before 2.0 (the sample of 2026-10-09) has no ``ev``: the investment
    reads, its offers' events do not."""
    service.get(SMOLNA).respond(200, json=body("api.map_inv_visible"))
    api = InvestmentsApi(http)

    assert len(api.investment(InvestmentSlug("smolna")).offers) == 3
    with pytest.raises(UnexpectedResponseError, match="kontraktu") as caught:
        api.price_events_of_offers(InvestmentSlug("smolna"))

    assert caught.value.detail == (
        "/api/map/investments/visible/smolna: sale.0.ev: Field required; "
        "sale.1.ev: Field required; sale.2.ev: Field required"
    )
