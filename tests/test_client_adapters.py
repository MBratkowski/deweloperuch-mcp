"""The JSON and RSC adapters: URLs as in the samples' requests, headers, decoding to DTOs.

Bodies are the samples from docs/discovery/samples/ (without trimming markers); the
network is mocked with respx.
"""

import contextlib
import json
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx

from deweloperuch_mcp import identity
from deweloperuch_mcp.allowlist import match_api, match_dump, match_page
from deweloperuch_mcp.client import dto, json_api, rsc
from deweloperuch_mcp.client.transport import HttpClient, path_segment
from deweloperuch_mcp.errors import (
    SERVICE_CHANGED,
    InvalidInputError,
    NotFoundError,
    UnexpectedResponseError,
)
from deweloperuch_mcp.flight import rsc_token
from deweloperuch_mcp.throttle import RequestLimiter
from discovery_samples import body, request_target, rsc_payload
from rsc_fixtures import OFFERS_UNKNOWN_CITY, OFFERS_WARSZAWA, UNKNOWN_CITY, offers_payload, raw


@pytest.fixture
def http(tmp_path: Path) -> Iterator[HttpClient]:
    limiter = RequestLimiter(tmp_path, min_interval=0, testing_only_allow_fast_interval=True)
    with HttpClient(limiter=limiter) as client:
        yield client


@pytest.fixture
def service() -> Iterator[respx.MockRouter]:
    with respx.mock(assert_all_called=False, assert_all_mocked=True) as router:
        yield router


def html_page(rsc_text: str) -> bytes:
    """``rsc_text`` inlined the way Next.js does it: raw UTF-8, not ``\\u`` escapes."""
    push = json.dumps(rsc_text, ensure_ascii=False)
    return (
        f"<!DOCTYPE html><html><body><script>self.__next_f.push([1,{push}])</script></body></html>"
    ).encode()


# --- JSON API: one function per endpoint ------------------------------------------------


@pytest.mark.parametrize(
    ("sample", "call", "model"),
    [
        ("api.cities_q", lambda http: json_api.cities(http, "krak", 8), dto.CitiesDto),
        (
            "api.location_search",
            lambda http: json_api.location_search(http, "mokot", 6),
            dto.LocationSearchDto,
        ),
        ("api.city_lookup", lambda http: json_api.city_lookup(http, "warszawa"), dto.CityLookupDto),
        (
            "api.city_districts",
            lambda http: json_api.city_districts(http, "warszawa"),
            dto.CityDistrictsDto,
        ),
        (
            "api.map_inv_visible",
            lambda http: json_api.investment(http, "smolna"),
            dto.InvestmentDto,
        ),
        (
            "api.inv_sale_events",
            lambda http: json_api.investment_sale_events(http, 33),
            dto.InvestmentSaleEventsDto,
        ),
        ("api.sale_events", lambda http: json_api.sale_events(http, 2377), dto.SaleEventsDto),
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


def test_query_values_are_percent_encoded(http: HttpClient, service: respx.MockRouter) -> None:
    url = identity.BASE_URL + "/api/cities?q=%C5%81%C3%B3d%C5%BA%20%26%20okolice&limit=8"
    route = service.get(url).respond(200, json=body("api.cities_q"))

    json_api.cities(http, "Łódź & okolice", 8)

    assert str(route.calls.last.request.url) == url


def test_path_segment_encodes_separators() -> None:
    assert path_segment("a/..?b#c") == "a%2F..%3Fb%23c"
    assert path_segment("smolna") == "smolna"


@pytest.mark.parametrize("slug", ["a/..?b", "..", "a b", "kraków"])
def test_slugs_with_separators_never_reach_the_service(
    http: HttpClient, service: respx.MockRouter, slug: str
) -> None:
    """Encoded, they cannot change the path; and the transport refuses encoded paths."""
    with pytest.raises(InvalidInputError):
        json_api.investment(http, slug)

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
        json_api.investment(http, "smolna")


# --- RSC: the offers list page ---------------------------------------------------------

FILTERED_PARAMS = [
    ("filterPrice", "500000-700000"),
    ("filterSize", "40-60"),
    ("sortBy", "amount"),
    ("sortOrder", "asc"),
    ("page", "2"),
    ("perPage", "50"),
]


def test_offers_list_requests_the_page_as_rsc_with_a_deterministic_token(
    http: HttpClient, service: respx.MockRouter
) -> None:
    target = request_target("page.offers_list.filtered")
    url = f"{identity.BASE_URL}{target}&_rsc={rsc_token(target)}"
    route = service.get(url).respond(
        200,
        content=offers_payload(body("page.offers_list.filtered")),
        headers={"Content-Type": "text/x-component"},
    )

    parsed = rsc.offers_list(http, "warszawa", FILTERED_PARAMS)

    assert parsed == dto.OffersPageDto.model_validate(body("page.offers_list.filtered"))
    request = route.calls.last.request
    assert str(request.url) == url
    assert request.headers.get_list("user-agent") == [identity.USER_AGENT]
    assert request.headers["rsc"] == "1"


def test_rsc_token_changes_with_the_query(http: HttpClient, service: respx.MockRouter) -> None:
    route = service.route(method="GET").respond(200, content=offers_payload())

    rsc.offers_list(http, "warszawa", [("perPage", "100")])
    rsc.offers_list(http, "warszawa", [("perPage", "50")])
    rsc.offers_list(http, "krakow", [("perPage", "100")])

    tokens = [call.request.url.params["_rsc"] for call in route.calls]
    assert len(set(tokens)) == 3
    for call in route.calls:
        url = call.request.url
        without_token = url.raw_path.decode().rsplit("&_rsc=", 1)[0]
        assert url.params["_rsc"] == rsc_token(without_token)


def test_html_instead_of_rsc_is_decoded_from_the_page_scripts(
    http: HttpClient, service: respx.MockRouter
) -> None:
    text = offers_payload(body("page.offers_list")).decode()
    service.route(method="GET").respond(
        200, content=html_page(text), headers={"Content-Type": "text/html; charset=utf-8"}
    )

    parsed = rsc.offers_list(http, "warszawa", [("perPage", "100")])

    assert parsed.pagination.total == 13324


# --- RSC: real payloads (tests/fixtures/rsc/) -------------------------------------------

RSC = {"Content-Type": "text/x-component"}
NOT_FOUND_ROW = b'f:E{"digest":"NEXT_HTTP_ERROR_FALLBACK;404"}\n'


def test_offers_list_parses_the_real_page(http: HttpClient, service: respx.MockRouter) -> None:
    """The data row follows JSON-LD text rows without a newline (the bug of 2026-10-10)."""
    service.route(method="GET").respond(200, content=raw(OFFERS_WARSZAWA), headers=RSC)

    parsed = rsc.offers_list(http, "warszawa", [("perPage", 10)])

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

    assert len(rsc.offers_list(http, "warszawa", []).data) == 10


def test_the_page_of_an_unknown_city_is_not_found(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """HTTP 200 without the data, with Next.js's 404 marker: no such page, not a change."""
    service.route(method="GET").respond(200, content=raw(OFFERS_UNKNOWN_CITY), headers=RSC)

    with pytest.raises(NotFoundError) as caught:
        rsc.offers_list(http, UNKNOWN_CITY, [("perPage", 10)])

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
        rsc.offers_list(http, UNKNOWN_CITY, [])


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
        rsc.offers_list(http, UNKNOWN_CITY, [])

    assert SERVICE_CHANGED in str(caught.value)


def test_the_data_wins_over_a_404_marker(http: HttpClient, service: respx.MockRouter) -> None:
    service.route(method="GET").respond(200, content=offers_payload() + NOT_FOUND_ROW)

    assert len(rsc.offers_list(http, "warszawa", []).data) == 10


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
        rsc.offers_list(http, "warszawa", [])

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

    assert rsc.offers_list(http, "warszawa", []).pagination.total == 13324


def test_prop_with_another_shape_is_unexpected(http: HttpClient, service: respx.MockRouter) -> None:
    service.route(method="GET").respond(200, content=offers_payload({"data": [], "paging": {}}))

    with pytest.raises(UnexpectedResponseError, match="kontrakt"):
        rsc.offers_list(http, "warszawa", [])


def test_city_with_separators_never_reaches_the_service(
    http: HttpClient, service: respx.MockRouter
) -> None:
    with pytest.raises(InvalidInputError):
        rsc.offers_list(http, "../api/map/powiat-sales/208", [])

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
        rsc.offers_list(http, "warszawa", [])


def test_every_adapter_requests_a_documented_read_channel(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """D1/D5: each adapter function stays on the read allowlist and off the dumps."""
    service.route(path__startswith="/api/").respond(200, json={})
    calls: list[Callable[[], object]] = [
        lambda: json_api.cities(http, "krak", 8),
        lambda: json_api.location_search(http, "mokot", 6),
        lambda: json_api.city_lookup(http, "warszawa"),
        lambda: json_api.city_districts(http, "warszawa"),
        lambda: json_api.investment(http, "smolna"),
        lambda: json_api.investment_sale_events(http, 33),
        lambda: json_api.sale_events(http, 2377),
        lambda: rsc.offers_list(http, "warszawa", [("page", 2)]),
    ]
    service.route(path__startswith="/ceny-ofertowe/").respond(200, content=offers_payload({}))

    for call in calls:
        with contextlib.suppress(UnexpectedResponseError):  # bodies are empty: paths matter
            call()

    paths = [call.request.url.path for call in service.calls]
    assert len(paths) == len(calls)
    for path in paths:
        assert match_api(path) is not None or match_page(path) is not None, path
        assert match_dump(path) is None, path


def test_every_adapter_request_carries_only_the_shared_user_agent(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """Behaviour check behind the static guard in tests/test_identity.py."""
    service.route(path__startswith="/api/cities").respond(200, json=body("api.cities_q"))
    service.route(path__startswith="/ceny-ofertowe/").respond(200, content=offers_payload())

    json_api.cities(http, "krak", 8)
    rsc.offers_list(http, "warszawa", [])

    requests: list[httpx.Request] = [call.request for call in service.calls]
    assert len(requests) == 2
    assert all(r.headers.get_list("user-agent") == [identity.USER_AGENT] for r in requests)
