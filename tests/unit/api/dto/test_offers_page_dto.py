"""Tests of ``deweloperuch_mcp.api.dto.offers_page_dto``."""

import datetime as dt
from typing import Any

import pytest
import respx

from deweloperuch_mcp import identity
from deweloperuch_mcp.api.dto.offers_page_dto import (
    OffersPageDto,
    SaleListItemDto,
    ServerPaginationDto,
)
from deweloperuch_mcp.api.http.transport import HttpClient
from deweloperuch_mcp.models.offer import DeveloperRef, InvestmentRef, ListedOffer, Offer
from deweloperuch_mcp.models.price_history import PriceChange, PriceHistory
from support.builders.offers import html_page, offers_list, offers_page
from support.providers.rsc import offers_payload
from support.providers.samples import body
from support.providers.service import LINKS, PAGES

RSC = {"Content-Type": "text/x-component"}
FILTERED = [
    ("filterPrice", "500000-700000"),
    ("filterSize", "40-60"),
    ("sortBy", "amount"),
    ("sortOrder", "asc"),
    ("page", "2"),
    ("perPage", "50"),
]


def first_row() -> dict[str, Any]:
    """The first row of the sample ``page.offers_list.v2_sales`` (Warszawa, 2026-10-31)."""
    row: dict[str, Any] = body("page.offers_list.v2_sales")[0]
    return row


def test_offers_list_requests_the_page_as_rsc_with_an_empty_rsc(
    http: HttpClient, service: respx.MockRouter
) -> None:
    page = offers_page(total=1192, page=2, per_page=50)
    target = HttpClient.target("/ceny-ofertowe/warszawa/mieszkania", FILTERED)
    url = f"{identity.BASE_URL}{target}&_rsc="
    route = service.get(url).respond(200, content=offers_payload(page), headers=RSC)

    parsed = offers_list(http, "warszawa", FILTERED)

    assert parsed == OffersPageDto.model_validate(page)
    request = route.calls.last.request
    assert str(request.url) == url
    assert request.headers.get_list("user-agent") == [identity.USER_AGENT]
    assert request.headers["rsc"] == "1"


def test_every_page_gets_the_same_empty_rsc_as_its_last_parameter(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """[P 2026-10-31] an empty ``_rsc`` returns the payload; the query before it still tells
    the pages apart (and their cache entries)."""
    route = service.route(method="GET").respond(200, content=offers_payload(), headers=RSC)

    offers_list(http, "warszawa", [("perPage", "100")])
    offers_list(http, "warszawa", [("perPage", "50")])
    offers_list(http, "krakow", [("perPage", "100")])

    assert [call.request.url.raw_path.decode() for call in route.calls] == [
        "/ceny-ofertowe/warszawa/mieszkania?perPage=100&_rsc=",
        "/ceny-ofertowe/warszawa/mieszkania?perPage=50&_rsc=",
        "/ceny-ofertowe/krakow/mieszkania?perPage=100&_rsc=",
    ]


def test_html_instead_of_rsc_is_decoded_from_the_page_scripts(
    http: HttpClient, service: respx.MockRouter
) -> None:
    text = offers_payload(offers_page()).decode()
    service.route(method="GET").respond(
        200, content=html_page(text), headers={"Content-Type": "text/html; charset=utf-8"}
    )

    parsed = offers_list(http, "warszawa", [("perPage", "10")])

    assert (parsed.serverPaginationData.totalCount, len(parsed.sales)) == (11_672, 10)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("PRICE_INCREASE", "increase"),
        ("PRICE_DECREASE", "decrease"),
        ("NO_CHANGE", "no_change"),
        ("NEW_OFFER", "new_offer"),
        ("PRICE_SOMETHING_NEW", "price_something_new"),
        ("", None),
        (None, None),
    ],
)
def test_change_kind(value: str | None, expected: str | None) -> None:
    assert SaleListItemDto._change_kind(value) == expected


def test_listed_offer_from_the_list_page() -> None:
    listed = SaleListItemDto.model_validate(first_row()).to_model()

    assert listed == ListedOffer(
        offer=Offer(
            offer_id=4487,
            name="A2",
            status="active",
            price=810660.0,
            currency="PLN",
            area_m2=35.4,
            history=PriceHistory(
                since_start=PriceChange(pln=660.0, percent=0.08),
                last_change=PriceChange(pln=49560.0, percent=6.51, direction="increase"),
                events_count=6,
                created_on=dt.date(2025, 2, 25),
                last_event_on=dt.date(2026, 10, 30),
                last_changed_on=dt.date(2026, 10, 30),
            ),
        ),
        investment=InvestmentRef(
            investment_slug="apartamenty-beethovena",
            name="Apartamenty Beethovena",
            city="Warszawa",
            city_slug="warszawa",
            district="Mokotów",
            developer=DeveloperRef(developer_slug="dom-development", name="Dom Development S.A."),
        ),
    )
    assert listed.offer.price_per_m2 == 22900.0
    assert listed.offer.history.events is None  # not fetched
    assert LINKS.investment(listed.investment) == (
        PAGES + "/warszawa/deweloperzy/dom-development/apartamenty-beethovena"
    )


@pytest.mark.parametrize("city_slug", ["", None])
def test_listed_offer_without_its_city_slug_has_no_investment_link(city_slug: str | None) -> None:
    """D12: an address is built from the item's own slugs or not at all, never guessed."""
    row = first_row()
    row["invest"]["city_slug"] = city_slug

    listed = SaleListItemDto.model_validate(row).to_model()

    assert listed.investment.city_slug is None
    assert LINKS.investment(listed.investment) is None


@pytest.mark.parametrize(("district", "expected"), [("", None), ("  ", None), (None, None)])
def test_an_investment_without_its_district_has_none(
    district: str | None, expected: str | None
) -> None:
    """The service writes ``""`` where an investment has no district (Sopot in the offer
    snapshot [P 2026-10-31]): no value, not a district."""
    row = first_row()
    row["invest"]["district"] = district

    listed = SaleListItemDto.model_validate(row).to_model()

    assert listed.investment.district is expected


@pytest.mark.parametrize(("price", "area"), [("", "35.4"), ("810660", ""), ("810660", "0")])
def test_price_per_m2_needs_price_and_area(price: str, area: str) -> None:
    row = first_row()
    row.update(amount=price, size=area)

    listed = SaleListItemDto.model_validate(row).to_model()

    assert listed.offer.price_per_m2 is None


def test_the_search_page_keeps_the_service_paging() -> None:
    """The page as the service paged it: its own page and page size (25 by default on 2.0,
    [P 2026-10-31]), whatever was asked for."""
    page = OffersPageDto.model_validate(
        {
            "sales": body("page.offers_list.v2_sales"),
            "serverPaginationData": body("page.offers_list.v2_pagination"),
        }
    ).to_model()

    assert (page.total, page.page, page.per_page, page.returned) == (11_672, 1, 25, 3)
    assert page.items[0].offer.offer_id == 4487


def test_the_paging_reads_what_the_model_needs() -> None:
    paging = ServerPaginationDto.model_validate(body("page.offers_list.v2_district_pagination"))

    assert (paging.currentPage, paging.perPage, paging.totalCount) == (1, 25, 959)
