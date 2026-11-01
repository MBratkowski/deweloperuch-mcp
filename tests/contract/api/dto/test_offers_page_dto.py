"""Contract of ``deweloperuch_mcp.api.dto.offers_page_dto`` with the service's real answers
(the samples in docs/discovery/samples/, the raw payloads in tests/fixtures/rsc/), as
``OffersApi`` reads them: the props ``sales`` and ``serverPaginationData`` of the 2.0
offers lists of a city and of a district [P 2026-10-31].
"""

import datetime as dt
import re
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from pydantic import ValidationError

from deweloperuch_mcp import identity
from deweloperuch_mcp.api.adapters.locations_api import LocationsApi
from deweloperuch_mcp.api.adapters.offers_api import OffersApi
from deweloperuch_mcp.api.dto.dto import Dto
from deweloperuch_mcp.api.dto.offers_page_dto import (
    OffersPageDto,
    SaleListItemDto,
    ServerPaginationDto,
)
from deweloperuch_mcp.api.http.transport import HttpClient
from deweloperuch_mcp.errors import (
    SERVICE_CHANGED,
    InvalidInputError,
    NotFoundError,
    UnexpectedResponseError,
)
from support.builders.offers import html_page, offers_list, real_props
from support.providers.rsc import (
    OFFERS_UNKNOWN_CITY_20261031,
    OFFERS_UNKNOWN_DISTRICT_20261031,
    OFFERS_WARSZAWA_20261031,
    OFFERS_WARSZAWA_MOKOTOW_20261031,
    UNKNOWN_CITY,
    offers_payload,
    raw,
)
from support.providers.samples import body, envelope, rsc_payload

RSC = {"Content-Type": "text/x-component"}
CITY_LIST = "/ceny-ofertowe/warszawa/mieszkania"
DISTRICT_LIST = "/ceny-ofertowe/warszawa/mokotow/mieszkania"
UNKNOWN_DISTRICT_LIST = "/ceny-ofertowe/warszawa/nieistniejaca-dzielnica/mieszkania"
NOT_FOUND_ROW = re.compile(rb'([0-9a-f]+):E\{"digest":"NEXT_HTTP_ERROR_FALLBACK;404"\}\n')
"""An error row with Next.js's 404 marker; the pages of an unknown city or district have two
[P 2026-10-31]."""
PAGES = [
    (OFFERS_WARSZAWA_20261031, CITY_LIST, 11_672),
    (OFFERS_WARSZAWA_MOKOTOW_20261031, DISTRICT_LIST, 959),
]
"""Each real list, its path, and its ``totalCount`` [P 2026-10-31]."""
CHANGE_KINDS = {"PRICE_INCREASE", "PRICE_DECREASE", "NO_CHANGE", "NEW_OFFER"}
"""``last_event_type`` [P 2026-10-31]: all four among 125 rows read (pages-rsc.md)."""


def read(http: HttpClient, service: respx.MockRouter, fixture: Path, path: str) -> OffersPageDto:
    service.route(method="GET").respond(200, content=raw(fixture), headers=RSC)
    return OffersApi(http).offers_page(path, [])


@pytest.mark.parametrize(("fixture", "path", "total"), PAGES)
def test_a_real_list_is_read_whole(
    http: HttpClient, service: respx.MockRouter, fixture: Path, path: str, total: int
) -> None:
    """Both props from one request; the service's default page is 25 offers [P 2026-10-31]."""
    parsed = read(http, service, fixture, path)

    paging = parsed.serverPaginationData
    assert (paging.currentPage, paging.perPage, paging.totalCount) == (1, 25, total)
    assert len(parsed.sales) == 25
    assert service.calls.call_count == 1
    assert service.calls.last.request.url.raw_path.decode() == f"{path}?_rsc="


@pytest.mark.parametrize(("fixture", "path", "total"), PAGES)
def test_every_row_of_a_real_list_has_the_fields_the_search_reads(
    http: HttpClient, service: respx.MockRouter, fixture: Path, path: str, total: int
) -> None:
    """Every row: the offer's id, label, status, price and area (numbers as text), the
    changes since the first price and the last one, the dates, the investment and its
    developer [P 2026-10-31]."""
    rows = read(http, service, fixture, path).sales

    for row in rows:
        assert row.sale_id > 0 and row.name and row.status == "active"
        assert isinstance(row.amount, str) and float(row.amount) > 0
        assert isinstance(row.size, str) and float(row.size) > 0
        assert row.currency == "PLN"
        for change in (
            row.start_amount_difference,
            row.start_amount_difference_percent,
            row.last_amount_difference,
            row.last_amount_difference_percent,
        ):
            assert isinstance(change, str) and change.strip()
        assert row.last_event_type in CHANGE_KINDS
        assert row.total_events is not None and row.total_events >= 1
        for day in (row.creation_date, row.last_event_date, row.last_change_event_date):
            assert day is not None and dt.date.fromisoformat(day) <= dt.date(2026, 10, 31)
        invest = row.invest
        assert invest.invest_id is not None and invest.name and invest.slug
        assert (invest.city, invest.city_slug) == ("Warszawa", "warszawa")
        assert invest.developer.developer_id is not None
        assert invest.developer.name and invest.developer.slug
        listed = row.to_model()
        assert listed.offer.price_per_m2 is not None and listed.offer.history.since_start.pln
        assert listed.offer.history.last_change.direction is not None


def test_the_first_row_of_the_city_list_as_sent(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """The first row of the real page, field by field: the sample ``page.offers_list.v2_sales``
    is that row."""
    first = read(http, service, OFFERS_WARSZAWA_20261031, CITY_LIST).sales[0]

    assert first == SaleListItemDto.model_validate(body("page.offers_list.v2_sales")[0])
    assert (first.sale_id, first.name, first.amount, first.size, first.currency) == (
        4487,
        "A2",
        "810660",
        "35.4",
        "PLN",
    )
    assert (first.start_amount_difference, first.start_amount_difference_percent) == (
        "660",
        "0.08",
    )
    assert (first.last_amount_difference, first.last_amount_difference_percent) == (
        "49560",
        "6.51",
    )
    assert (first.last_event_type, first.total_events, first.status) == (
        "PRICE_INCREASE",
        6,
        "active",
    )
    assert (first.creation_date, first.last_event_date, first.last_change_event_date) == (
        "2025-02-25",
        "2026-10-30",
        "2026-10-30",
    )
    assert (first.invest.invest_id, first.invest.name, first.invest.slug) == (
        55,
        "Apartamenty Beethovena",
        "apartamenty-beethovena",
    )
    assert (first.invest.city, first.invest.city_slug) == ("Warszawa", "warszawa")
    developer = first.invest.developer
    assert (developer.developer_id, developer.name, developer.slug) == (
        44,
        "Dom Development S.A.",
        "dom-development",
    )


@pytest.mark.parametrize(
    ("fixture", "path", "districts"),
    [
        (OFFERS_WARSZAWA_20261031, CITY_LIST, {"Mokotów", "Ursynów"}),
        (OFFERS_WARSZAWA_MOKOTOW_20261031, DISTRICT_LIST, {"Mokotów"}),
    ],
)
def test_every_row_names_the_district_of_its_investment(
    http: HttpClient, service: respx.MockRouter, fixture: Path, path: str, districts: set[str]
) -> None:
    """``invest.district`` [P 2026-10-31]: a name as the locations search gives it, in every
    row of both lists; on the district's list, the district itself."""
    rows = read(http, service, fixture, path).sales

    assert {row.invest.district for row in rows} == districts
    assert {row.to_model().investment.district for row in rows} == districts


def test_the_city_list_is_in_the_service_order_without_a_sort() -> None:
    """[P 2026-10-31] pages-rsc.md: no ``sortBy`` lists the offers by ``sale_id``, ascending."""
    ids = [row["sale_id"] for row in real_props()["sales"]]

    assert ids == sorted(ids) and len(set(ids)) == 25


def test_the_district_list_holds_the_offers_of_the_district() -> None:
    """[P 2026-10-31] the district's route lists the district's offers: every row's
    investment is in Mokotów (``invest.district``, which the search does not show), and
    ``totalCount`` 959 is the count of Mokotów in the offer snapshot of the same day."""
    props = real_props(OFFERS_WARSZAWA_MOKOTOW_20261031)

    assert {row["invest"]["district"] for row in props["sales"]} == {"Mokotów"}
    assert props["serverPaginationData"]["totalCount"] == 959


def test_the_rows_refuse_the_trimming_marker_of_the_sample() -> None:
    """The sample ``page.offers_list.v2_sales`` ends with ``"... (22 more, 25 total)"``: never
    an offer."""
    page = {
        "sales": envelope("page.offers_list.v2_sales")["value"],
        "serverPaginationData": body("page.offers_list.v2_pagination"),
    }

    with pytest.raises(ValidationError):
        OffersPageDto.model_validate(page)


def test_the_samples_are_the_props_of_the_real_pages() -> None:
    city, district = real_props(), real_props(OFFERS_WARSZAWA_MOKOTOW_20261031)

    assert body("page.offers_list.v2_sales") == city["sales"][:3]
    assert body("page.offers_list.v2_pagination") == city["serverPaginationData"]
    assert body("page.offers_list.v2_district_pagination") == district["serverPaginationData"]
    for sample in ("page.offers_list.v2_pagination", "page.offers_list.v2_district_pagination"):
        paging = Dto.validated(ServerPaginationDto, body(sample), sample)
        assert (paging.currentPage, paging.perPage) == (1, 25)


@pytest.mark.parametrize(
    ("fixture", "path"),
    [
        (OFFERS_UNKNOWN_CITY_20261031, f"/ceny-ofertowe/{UNKNOWN_CITY}/mieszkania"),
        (OFFERS_UNKNOWN_DISTRICT_20261031, UNKNOWN_DISTRICT_LIST),
    ],
)
def test_the_list_of_an_unknown_city_or_district_is_not_found(
    http: HttpClient, service: respx.MockRouter, fixture: Path, path: str
) -> None:
    """HTTP 200 without the props, with Next.js's 404 marker [P 2026-10-31]: no such list,
    not a change of the service."""
    with pytest.raises(NotFoundError) as caught:
        read(http, service, fixture, path)

    assert str(caught.value) == "Serwis nie zna żądanych danych (strona nie istnieje)."
    assert caught.value.detail == (
        f"{path}: brak propsów 'sales', 'serverPaginationData', strona zgłasza "
        "NEXT_HTTP_ERROR_FALLBACK;404"
    )


def test_the_page_of_an_unknown_city_served_as_html_is_not_found_too(
    http: HttpClient, service: respx.MockRouter
) -> None:
    service.route(method="GET").respond(
        200,
        content=html_page(raw(OFFERS_UNKNOWN_CITY_20261031).decode()),
        headers={"Content-Type": "text/html; charset=utf-8"},
    )

    with pytest.raises(NotFoundError):
        offers_list(http, UNKNOWN_CITY, [])


def test_the_real_page_served_as_html_is_read_too(
    http: HttpClient, service: respx.MockRouter
) -> None:
    service.route(method="GET").respond(
        200,
        content=html_page(raw(OFFERS_WARSZAWA_20261031).decode()),
        headers={"Content-Type": "text/html; charset=utf-8"},
    )

    assert len(offers_list(http, "warszawa", []).sales) == 25


@pytest.mark.parametrize(
    "marker",
    [
        b"",  # no error row at all
        b'\\1:E{"digest":"NEXT_HTTP_ERROR_FALLBACK;403"}\n',
        b'\\1:E{"digest":"2417303245"}\n',  # a server error
        b'\\1:{"digest":"NEXT_HTTP_ERROR_FALLBACK;404"}\n',  # not an error row
    ],
)
def test_a_page_without_the_props_nor_the_404_marker_is_unexpected(
    http: HttpClient, service: respx.MockRouter, marker: bytes
) -> None:
    """Like the answer to ``filterDistrict`` on 2.0 (a page without ``sales``, [P 2026-10-31];
    whether it has the marker was not read): without the marker, a changed page."""
    payload, found = NOT_FOUND_ROW.subn(marker, raw(OFFERS_UNKNOWN_CITY_20261031))
    assert found == 2
    service.route(method="GET").respond(200, content=payload, headers=RSC)

    with pytest.raises(UnexpectedResponseError) as caught:
        offers_list(http, UNKNOWN_CITY, [])

    assert SERVICE_CHANGED in str(caught.value)
    assert "sales" not in str(caught.value)


def test_the_props_win_over_a_404_marker(http: HttpClient, service: respx.MockRouter) -> None:
    marker = b'ff:E{"digest":"NEXT_HTTP_ERROR_FALLBACK;404"}\n'
    service.route(method="GET").respond(200, content=offers_payload() + marker, headers=RSC)

    assert len(offers_list(http, "warszawa", []).sales) == 25


@pytest.mark.parametrize(
    ("props", "detail"),
    [
        (
            {"sales": body("page.offers_list.v2_sales")},
            "w propsie 'serverPaginationData' (propsy z danymi: sales)",
        ),
        (
            {"serverPaginationData": body("page.offers_list.v2_pagination")},
            "w propsie 'sales' (propsy z danymi: serverPaginationData)",
        ),
        (
            {"initialData": {"data": [], "pagination": {}}},
            "w propsach 'sales', 'serverPaginationData' (propsy z danymi: initialData)",
        ),
    ],
)
def test_a_page_without_one_of_the_props_is_unexpected(
    http: HttpClient, service: respx.MockRouter, props: dict[str, Any], detail: str
) -> None:
    """Both props or none: the 1.0 prop ``initialData`` alone is a changed page too."""
    service.route(method="GET").respond(200, content=rsc_payload(props))

    with pytest.raises(UnexpectedResponseError) as caught:
        offers_list(http, "warszawa", [])

    assert caught.value.detail == f"{CITY_LIST} nie zawiera danych {detail}"
    assert "sales" not in str(caught.value)


@pytest.mark.parametrize(
    "page",
    [
        {"serverPaginationData": {"page": 1, "perPage": 25, "total": 11672}},  # the 1.0 names
        {"serverPaginationData": {"currentPage": 1, "perPage": "dużo", "totalCount": 11672}},
        {"sales": [{"sale_id": 1}]},
    ],
)
def test_props_of_another_shape_are_unexpected(
    http: HttpClient, service: respx.MockRouter, page: dict[str, Any]
) -> None:
    service.route(method="GET").respond(200, content=offers_payload(page), headers=RSC)

    with pytest.raises(UnexpectedResponseError, match="kontrakt") as caught:
        offers_list(http, "warszawa", [])

    assert caught.value.detail is not None
    assert caught.value.detail.startswith(f"{CITY_LIST} (propsy sales, serverPaginationData): ")


def test_an_empty_page_is_read() -> None:
    """A list with nothing to show: no rows and the counts (the shape of an empty answer was
    not seen: the live suite reads one)."""
    page = OffersPageDto.model_validate(
        {
            "sales": [],
            "serverPaginationData": {
                "currentPage": 1,
                "perPage": 10,
                "totalCount": 0,
                "totalPages": 0,
                "startItem": 0,
                "endItem": 0,
            },
        }
    ).to_model()

    assert (page.items, page.total, page.page, page.per_page) == ((), 0, 1, 10)


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


@pytest.mark.parametrize("frame", [OFFERS_WARSZAWA_20261031, OFFERS_WARSZAWA_MOKOTOW_20261031])
def test_splicing_the_real_props_back_gives_the_real_page(frame: Path) -> None:
    """The frames the routes splice pages into (``offers_payload``) are encoded as the
    service encodes them: with their own props they are the fixtures, byte for byte."""
    props = real_props(frame)

    spliced = {"sales": props["sales"], "serverPaginationData": props["serverPaginationData"]}
    assert offers_payload(spliced, frame) == raw(frame)
