"""Tests of ``deweloperuch_mcp.api.dto.offers_page_dto``."""

import datetime as dt

import pytest
import respx

from deweloperuch_mcp import identity
from deweloperuch_mcp.api.dto import offers_page_dto
from deweloperuch_mcp.api.dto.offers_page_dto import SaleListItemDto
from deweloperuch_mcp.api.http.transport import HttpClient
from deweloperuch_mcp.flight import rsc_token
from deweloperuch_mcp.models.offer import DeveloperRef, InvestmentRef, ListedOffer, Offer
from deweloperuch_mcp.models.price_history import PriceChange, PriceHistory
from support.builders.offers import html_page, offers_list
from support.providers.rsc import offers_payload
from support.providers.samples import body, request_target
from support.providers.service import LINKS, PAGES

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

    parsed = offers_list(http, "warszawa", FILTERED_PARAMS)

    assert parsed == offers_page_dto.OffersPageDto.model_validate(body("page.offers_list.filtered"))
    request = route.calls.last.request
    assert str(request.url) == url
    assert request.headers.get_list("user-agent") == [identity.USER_AGENT]
    assert request.headers["rsc"] == "1"


def test_rsc_token_changes_with_the_query(http: HttpClient, service: respx.MockRouter) -> None:
    route = service.route(method="GET").respond(200, content=offers_payload())

    offers_list(http, "warszawa", [("perPage", "100")])
    offers_list(http, "warszawa", [("perPage", "50")])
    offers_list(http, "krakow", [("perPage", "100")])

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

    parsed = offers_list(http, "warszawa", [("perPage", "100")])

    assert parsed.pagination.total == 13324


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("PRICE_INCREASE", "increase"),
        ("PRICE_DECREASE", "decrease"),
        ("NO_CHANGE", "no_change"),
        ("PRICE_SOMETHING_NEW", "price_something_new"),
        ("", None),
        (None, None),
    ],
)
def test_change_kind(value: str | None, expected: str | None) -> None:
    assert SaleListItemDto._change_kind(value) == expected


def test_listed_offer_from_the_list_page() -> None:
    item = offers_page_dto.OffersPageDto.model_validate(body("page.offers_list")).data[0]

    listed = item.to_model()

    assert listed == ListedOffer(
        offer=Offer(
            offer_id=4397,
            name="D1.1.1.4",
            status="active",
            price=994012.0,
            currency="PLN",
            area_m2=55.25,
            history=PriceHistory(
                since_start=PriceChange(pln=-5988.0, percent=-0.6),
                last_change=PriceChange(pln=55250.0, percent=5.89, direction="increase"),
                events_count=12,
                created_on=dt.date(2025, 5, 1),
                last_event_on=dt.date(2026, 10, 3),
                last_changed_on=dt.date(2026, 10, 3),
            ),
        ),
        investment=InvestmentRef(
            investment_slug="nowy-targowek-vi",
            name="Nowy Targówek VI",
            city="Warszawa",
            city_slug="warszawa",
            developer=DeveloperRef(developer_slug="atal", name="ATAL S.A."),
        ),
    )
    assert listed.offer.price_per_m2 == 17991.17
    assert listed.offer.history.events is None  # not fetched
    assert LINKS.investment(listed.investment) == (
        PAGES + "/warszawa/deweloperzy/atal/nowy-targowek-vi"
    )


@pytest.mark.parametrize("city_slug", ["", None])
def test_listed_offer_without_its_city_slug_has_no_investment_link(city_slug: str | None) -> None:
    """D12: an address is built from the item's own slugs or not at all, never guessed."""
    item = body("page.offers_list")["data"][0]
    item["invest"]["city_slug"] = city_slug

    listed = offers_page_dto.SaleListItemDto.model_validate(item).to_model()

    assert listed.investment.city_slug is None
    assert LINKS.investment(listed.investment) is None


@pytest.mark.parametrize(("price", "area"), [("", "55.25"), ("994012", ""), ("994012", "0")])
def test_price_per_m2_needs_price_and_area(price: str, area: str) -> None:
    item = body("page.offers_list")["data"][0]
    item.update(amount=price, size=area)

    listed = offers_page_dto.SaleListItemDto.model_validate(item).to_model()

    assert listed.offer.price_per_m2 is None


def test_the_search_page_keeps_the_service_paging() -> None:
    page = offers_page_dto.OffersPageDto.model_validate(
        body("page.offers_list.filtered")
    ).to_model()

    assert (page.total, page.page, page.per_page, page.returned) == (1192, 2, 50, 3)
    assert page.items[0].offer.offer_id == 120306
