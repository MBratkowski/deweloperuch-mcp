"""Contract of ``deweloperuch_mcp.api.dto.offers_page_dto`` with the service's real answers
(the samples in docs/discovery/samples/, the raw payloads in tests/fixtures/).
"""

import json
from typing import Any

import httpx
import pytest
import respx

from deweloperuch_mcp import identity
from deweloperuch_mcp.api.adapters.locations_api import LocationsApi
from deweloperuch_mcp.api.dto import (
    offers_page_dto,
)
from deweloperuch_mcp.api.http.transport import HttpClient
from deweloperuch_mcp.errors import (
    SERVICE_CHANGED,
    InvalidInputError,
    NotFoundError,
    UnexpectedResponseError,
)
from support.builders.offers import html_page, offers_list
from support.providers.rsc import (
    OFFERS_UNKNOWN_CITY,
    OFFERS_WARSZAWA,
    UNKNOWN_CITY,
    offers_payload,
    raw,
)
from support.providers.samples import body, rsc_payload

RSC = {"Content-Type": "text/x-component"}


NOT_FOUND_ROW = b'f:E{"digest":"NEXT_HTTP_ERROR_FALLBACK;404"}\n'


def test_offers_list_parses_the_real_page(http: HttpClient, service: respx.MockRouter) -> None:
    """The data row follows JSON-LD text rows without a newline (the bug of 2026-10-10)."""
    service.route(method="GET").respond(200, content=raw(OFFERS_WARSZAWA), headers=RSC)

    parsed = offers_list(http, "warszawa", [("perPage", 10)])

    assert len(parsed.data) == 10
    assert (parsed.pagination.page, parsed.pagination.perPage) == (1, 10)
    assert (parsed.pagination.total, parsed.pagination.totalPages) == (13324, 20)
    assert parsed.data[0].sale_id == 4397
    assert all(offer.invest.city_slug == "warszawa" for offer in parsed.data)


def test_the_real_page_served_as_html_is_parsed_too(
    http: HttpClient, service: respx.MockRouter
) -> None:
    service.route(method="GET").respond(
        200,
        content=html_page(raw(OFFERS_WARSZAWA).decode()),
        headers={"Content-Type": "text/html; charset=utf-8"},
    )

    assert len(offers_list(http, "warszawa", []).data) == 10


def test_the_page_of_an_unknown_city_is_not_found(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """HTTP 200 without the data, with Next.js's 404 marker: no such page, not a change."""
    service.route(method="GET").respond(200, content=raw(OFFERS_UNKNOWN_CITY), headers=RSC)

    with pytest.raises(NotFoundError) as caught:
        offers_list(http, UNKNOWN_CITY, [("perPage", 10)])

    assert str(caught.value) == "Serwis nie zna żądanych danych (strona nie istnieje)."
    assert caught.value.detail == (
        f"/ceny-ofertowe/{UNKNOWN_CITY}/mieszkania: brak propsa 'initialData', strona "
        "zgłasza NEXT_HTTP_ERROR_FALLBACK;404"
    )


def test_the_page_of_an_unknown_city_served_as_html_is_not_found_too(
    http: HttpClient, service: respx.MockRouter
) -> None:
    service.route(method="GET").respond(
        200,
        content=html_page(raw(OFFERS_UNKNOWN_CITY).decode()),
        headers={"Content-Type": "text/html; charset=utf-8"},
    )

    with pytest.raises(NotFoundError):
        offers_list(http, UNKNOWN_CITY, [])


@pytest.mark.parametrize(
    "marker",
    [
        b"",  # no error row at all
        b'f:E{"digest":"NEXT_HTTP_ERROR_FALLBACK;403"}\n',
        b'f:E{"digest":"2417303245"}\n',  # a server error
        b'f:{"digest":"NEXT_HTTP_ERROR_FALLBACK;404"}\n',  # not an error row
    ],
)
def test_a_page_without_the_data_nor_the_404_marker_is_unexpected(
    http: HttpClient, service: respx.MockRouter, marker: bytes
) -> None:
    payload = raw(OFFERS_UNKNOWN_CITY)
    assert payload.count(NOT_FOUND_ROW) == 1
    service.route(method="GET").respond(
        200, content=payload.replace(NOT_FOUND_ROW, marker), headers=RSC
    )

    with pytest.raises(UnexpectedResponseError) as caught:
        offers_list(http, UNKNOWN_CITY, [])

    assert SERVICE_CHANGED in str(caught.value)


def test_the_data_wins_over_a_404_marker(http: HttpClient, service: respx.MockRouter) -> None:
    service.route(method="GET").respond(200, content=offers_payload() + NOT_FOUND_ROW)

    assert len(offers_list(http, "warszawa", []).data) == 10


@pytest.mark.parametrize(
    ("props", "data_props"),
    [
        ({"serverPaginationData": {"page": 1}}, "serverPaginationData"),
        ({"initialData": "$f:props:initialData"}, "brak"),
    ],
)
def test_page_without_the_prop_is_unexpected(
    http: HttpClient, service: respx.MockRouter, props: dict[str, Any], data_props: str
) -> None:
    payload = rsc_payload(props).replace(b'"initialData":"$2:props:initialData"', b'"x":1')
    service.route(method="GET").respond(200, content=payload)

    with pytest.raises(UnexpectedResponseError) as caught:
        offers_list(http, "warszawa", [])

    detail = caught.value.detail
    assert detail is not None
    assert "nie zawiera danych w propsie 'initialData'" in detail
    assert f"(propsy z danymi: {data_props})" in detail
    assert "initialData" not in str(caught.value)


def test_reference_before_the_data_is_skipped(http: HttpClient, service: respx.MockRouter) -> None:
    """Props may hold references (``"$2:props:..."``); the data is the object-valued one."""
    data = json.dumps(body("page.offers_list"), separators=(",", ":"))
    payload = (
        '1f:I[4242,["static/chunks/4242.js"],"OffersList"]\n'
        '2:["$","div",null,{"children":['
        '["$","$L1f",null,{"initialData":"$3:props:initialData"}],'
        f'["$","$L1f",null,{{"initialData":{data}}}]]}}]\n'
    )
    service.route(method="GET").respond(200, content=payload.encode())

    assert offers_list(http, "warszawa", []).pagination.total == 13324


def test_prop_with_another_shape_is_unexpected(http: HttpClient, service: respx.MockRouter) -> None:
    service.route(method="GET").respond(200, content=offers_payload({"data": [], "paging": {}}))

    with pytest.raises(UnexpectedResponseError, match="kontrakt"):
        offers_list(http, "warszawa", [])


def test_city_with_separators_never_reaches_the_service(
    http: HttpClient, service: respx.MockRouter
) -> None:
    with pytest.raises(InvalidInputError):
        offers_list(http, "../api/map/powiat-sales/208", [])

    assert service.calls.call_count == 0


def test_html_with_unreadable_flight_data_is_unexpected(
    http: HttpClient, service: respx.MockRouter
) -> None:
    page = (
        b'<!DOCTYPE html><html><body><script>self.__next_f.push([1,"\\x"])</script></body></html>'
    )
    service.route(method="GET").respond(
        200, content=page, headers={"Content-Type": "text/html; charset=utf-8"}
    )

    with pytest.raises(UnexpectedResponseError, match="nieczytelnymi"):
        offers_list(http, "warszawa", [])


def test_every_adapter_request_carries_only_the_shared_user_agent(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """Behaviour check behind the static guard in tests/architecture/test_identity.py."""
    service.route(path__startswith="/api/cities").respond(200, json=body("api.cities_q"))
    service.route(path__startswith="/ceny-ofertowe/").respond(200, content=offers_payload())

    LocationsApi(http).city_search("krak", 8)
    offers_list(http, "warszawa", [])

    requests: list[httpx.Request] = [call.request for call in service.calls]
    assert len(requests) == 2
    assert all(r.headers.get_list("user-agent") == [identity.USER_AGENT] for r in requests)


@pytest.mark.parametrize(
    ("name", "first_offer", "pagination"),
    [
        ("page.offers_list", 4397, (1, 100, 13324, 20)),
        ("page.offers_list.filtered", 120306, (2, 50, 1192, 20)),
    ],
)
def test_offers_page_samples(
    name: str, first_offer: int, pagination: tuple[int, int, int, int]
) -> None:
    parsed = offers_page_dto.OffersPageDto.model_validate(body(name))

    page = parsed.pagination
    assert (page.page, page.perPage, page.total, page.totalPages) == pagination
    assert len(parsed.data) == 3
    first = parsed.data[0]
    assert first.sale_id == first_offer
    assert first.invest.slug
    assert first.invest.developer.slug
    assert isinstance(first.amount, str)
    assert first.last_event_type in ("PRICE_INCREASE", "PRICE_DECREASE", "NO_CHANGE")


def test_offers_page_sample_fields() -> None:
    first = offers_page_dto.OffersPageDto.model_validate(body("page.offers_list")).data[0]

    assert (first.name, first.amount, first.size, first.currency) == (
        "D1.1.1.4",
        "994012",
        "55.25",
        "PLN",
    )
    assert (first.start_amount_difference, first.start_amount_difference_percent) == (
        "-5988",
        "-0.6",
    )
    assert (first.last_amount_difference, first.last_amount_difference_percent) == (
        "55250",
        "5.89",
    )
    assert (first.total_events, first.status) == (12, "active")
    assert (first.creation_date, first.last_event_date, first.last_change_event_date) == (
        "2025-05-01",
        "2026-10-03",
        "2026-10-03",
    )
    assert (first.invest.invest_id, first.invest.name, first.invest.city_slug) == (
        54,
        "Nowy Targówek VI",
        "warszawa",
    )
    assert (first.invest.developer.name, first.invest.developer.slug) == ("ATAL S.A.", "atal")
