"""The views the CLI prints with ``--json`` and the MCP presenter cuts down (``views``):
domain names only (D3), immutable, built from what the use cases return. Their exact
output is pinned by the goldens (tests/golden/).
"""

import dataclasses
import json
import re
from typing import Any

import pytest
from pydantic import BaseModel

from deweloperuch_mcp.application.investments import FoundInvestment
from deweloperuch_mcp.application.offers import FoundOffer, FoundOffers
from deweloperuch_mcp.domain.investments import OfferDetail
from deweloperuch_mcp.domain.locations import LocationMatches, LocationSearchResult
from deweloperuch_mcp.domain.values import LocationQuery, OfferId
from deweloperuch_mcp.infrastructure.deweloperuch import dto, mappers
from deweloperuch_mcp.interfaces import views
from discovery_samples import body

BACKEND_KEY = re.compile(r"^(invest|sale)(_|$)|sale|amount|size|sqm|^data$")
BACKEND_VALUES = ("PRICE_INCREASE", "OFFER_EVENT", "ARCHIVED_EVENT", "ANNOUCMENT")


def keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {k for item in value.values() for k in keys(item)}
    if isinstance(value, list):
        return {k for item in value for k in keys(item)}
    return set()


def view_results() -> list[BaseModel]:
    investment = mappers.investment(dto.InvestmentDto.model_validate(body("api.map_inv_visible")))
    histories = dto.InvestmentSaleEventsDto.model_validate(body("api.inv_sale_events")).root
    events = {offer_id: mappers.price_events(items) for offer_id, items in histories.items()}
    one = dto.SaleEventsDto.model_validate(body("api.sale_events")).events
    found_offer = investment.find_offer(OfferId(2377))
    assert found_offer is not None
    page = mappers.offer_search_page(dto.OffersPageDto.model_validate(body("page.offers_list")))
    suggestions = dto.LocationSearchDto.model_validate(body("api.location_search")).suggestions
    places = LocationMatches(tuple(mappers.location_from_suggestion(s) for s in suggestions))
    return [
        views.investment(
            FoundInvestment(investment.listing().with_price_events(events), "url", "url")
        ),
        views.offer_detail(
            FoundOffer(
                OfferDetail(
                    offer=found_offer.with_price_events(mappers.price_events(one)),
                    investment=investment,
                ),
                "url",
                "url",
            )
        ),
        views.offer_search(FoundOffers(page, None, "url", ("url",) * len(page.items))),
        views.location_search(LocationSearchResult.of(LocationQuery("mokot"), places)),
    ]


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


def test_the_statistics_view_has_the_fields_the_cli_prints_in_order() -> None:
    """``--json`` prints ``dataclasses.asdict`` of it: the order is the output's order."""
    assert [field.name for field in dataclasses.fields(views.GovernmentStatistics)] == [
        "location_slug",
        "location_name",
        "dataset",
        "title",
        "source",
        "frequency",
        "total",
        "returned",
        "truncated",
        "available_from",
        "hint",
        "note",
        "stats_url",
        "series",
    ]
