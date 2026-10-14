"""Tests of ``deweloperuch_mcp.consumers.shared.offer_views``."""

import json
import re
from typing import Any

import pytest
from pydantic import BaseModel

from deweloperuch_mcp.api.dto import (
    developer_page_dto,
    investment_dto,
    offers_page_dto,
    sale_events_dto,
)
from deweloperuch_mcp.api.dto.city_sales_dto import CitySalesDto
from deweloperuch_mcp.api.dto.investment_sale_events_dto import InvestmentSaleEventsDto
from deweloperuch_mcp.api.dto.location_search_dto import LocationSearchDto
from deweloperuch_mcp.api.dto.sale_events_dto import SaleEventDto
from deweloperuch_mcp.consumers.mcp.presenters.get_investment_mcp_presenter import (
    InvestmentOfferItem,
    InvestmentResult,
)
from deweloperuch_mcp.consumers.mcp.presenters.get_offer_mcp_presenter import (
    OfferResult,
    PriceEventItem,
)
from deweloperuch_mcp.consumers.mcp.presenters.search_locations_mcp_presenter import (
    LocationItem,
    LocationsResult,
)
from deweloperuch_mcp.consumers.mcp.presenters.search_offers_mcp_presenter import (
    OfferItem,
    OffersResult,
)
from deweloperuch_mcp.consumers.shared.developer_views import DeveloperProfileView
from deweloperuch_mcp.consumers.shared.investment_views import InvestmentView
from deweloperuch_mcp.consumers.shared.location_views import LocationSearchView, LocationView
from deweloperuch_mcp.consumers.shared.market_views import MarketStatisticsView
from deweloperuch_mcp.consumers.shared.offer_views import (
    OfferDetailView,
    OfferSearchView,
    OfferSummaryView,
    OfferView,
    PriceEventView,
)
from deweloperuch_mcp.flight import component_props
from deweloperuch_mcp.models.investment import OfferDetail
from deweloperuch_mcp.models.location import LocationSearchResult
from deweloperuch_mcp.models.market_statistics import MarketCriteria
from deweloperuch_mcp.models.values import (
    CitySlug,
    InvestmentsLimit,
    LocationQuery,
    OfferId,
)
from deweloperuch_mcp.usecases.get_developer import GetDeveloperResult
from deweloperuch_mcp.usecases.get_investment import GetInvestmentResult
from deweloperuch_mcp.usecases.get_market_statistics import GetMarketStatisticsResult
from deweloperuch_mcp.usecases.get_offer import GetOfferResult
from deweloperuch_mcp.usecases.search_locations import SearchLocationsResult
from deweloperuch_mcp.usecases.search_offers import SearchOffersRequest, SearchOffersResult
from support.providers.rsc import CITY_SALES, DEVELOPER_POLSKA, raw
from support.providers.samples import body

BACKEND_KEY = re.compile(r"^(invest|sale)(_|$)|sale|amount|size|sqm|^data$")


BACKEND_VALUES = ("PRICE_INCREASE", "OFFER_EVENT", "ARCHIVED_EVENT", "ANNOUCMENT")


def keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {k for item in value.values() for k in keys(item)}
    if isinstance(value, list):
        return {k for item in value for k in keys(item)}
    return set()


def view_results() -> list[BaseModel]:
    investment = investment_dto.InvestmentDto.model_validate(body("api.map_inv_visible")).to_model()
    histories = InvestmentSaleEventsDto.model_validate(body("api.inv_sale_events")).root
    events = {offer_id: SaleEventDto.price_events(items) for offer_id, items in histories.items()}
    one = sale_events_dto.SaleEventsDto.model_validate(body("api.sale_events")).events
    found_offer = investment.find_offer(OfferId(2377))
    assert found_offer is not None
    page = offers_page_dto.OffersPageDto.model_validate(body("page.offers_list")).to_model()
    places = LocationSearchDto.model_validate(body("api.location_search")).to_model(limit=6)
    props = component_props(raw(DEVELOPER_POLSKA))
    developer = next(v for k, v in props if k == "data" and isinstance(v, dict))
    profile = developer_page_dto.DeveloperPageDto.model_validate(developer).to_model(
        CitySlug("polska")
    )
    listing = profile.listing(InvestmentsLimit(5))
    sales = CitySalesDto.model_validate_json(CITY_SALES["krakow"].read_bytes())
    market = sales.to_model(CitySlug("krakow")).statistics(MarketCriteria(city=CitySlug("krakow")))
    return [
        InvestmentView.from_result(
            GetInvestmentResult(
                listing=investment.listing().with_price_events(events),
                investment_url="url",
                developer_url="url",
            )
        ),
        OfferDetailView.from_result(
            GetOfferResult(
                detail=OfferDetail(
                    offer=found_offer.with_price_events(SaleEventDto.price_events(one)),
                    investment=investment,
                ),
                investment_url="url",
                developer_url="url",
                price_flags=None,
            )
        ),
        OfferSearchView.from_result(
            SearchOffersResult(
                criteria=SearchOffersRequest.parse(city="warszawa").criteria,
                page=page,
                list_url="url",
                investment_urls=("url",) * len(page.items),
            )
        ),
        LocationSearchView.from_result(
            SearchLocationsResult(found=LocationSearchResult.of(LocationQuery("mokot"), places))
        ),
        DeveloperProfileView.from_result(
            GetDeveloperResult(listing=listing, developer_url="url", investment_urls=("url",) * 5)
        ),
        MarketStatisticsView.from_result(
            GetMarketStatisticsResult(
                statistics=market, list_url="url", developer_urls=("url",) * 10
            )
        ),
    ]


@pytest.mark.usefixtures("unix_sockets_for_the_event_loop")
@pytest.mark.parametrize(
    ("shown", "domain", "added"),
    [
        (LocationsResult, LocationSearchView, set()),
        (LocationItem, LocationView, set()),
        (OffersResult, OfferSearchView, set()),
        (OfferItem, OfferSummaryView, set()),
        (OfferResult, OfferDetailView, set()),
        (PriceEventItem, PriceEventView, set()),
        (InvestmentResult, InvestmentView, {"offers_returned", "truncated"}),
        (InvestmentOfferItem, OfferView, set()),
    ],
)
def test_mcp_results_keep_the_domain_field_names(
    shown: type[BaseModel], domain: type[BaseModel], added: set[str]
) -> None:
    """D3: the representation only drops fields of the views the CLI prints whole (and
    adds the D4 counters)."""
    assert set(shown.model_fields) - added <= set(domain.model_fields)
    assert added <= set(shown.model_fields)


def test_views_have_no_backend_names() -> None:
    for result in view_results():
        dumped = result.model_dump(mode="json")
        backend = {key for key in keys(dumped) if BACKEND_KEY.search(key)}
        assert backend == set(), type(result).__name__
        text = json.dumps(dumped)
        assert not [value for value in BACKEND_VALUES if value in text]


def test_views_are_immutable() -> None:
    investment = view_results()[0]

    with pytest.raises(ValueError, match="frozen"):
        investment.name = "x"  # type: ignore[attr-defined]
