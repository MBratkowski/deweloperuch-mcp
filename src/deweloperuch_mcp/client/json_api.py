"""JSON API adapter (channel A, D1): one function per ``GET /api/*`` endpoint, returning DTOs.

Only read endpoints from docs/discovery/endpoints.md, all [P], called with the query
parameters their samples were captured with. Parameters the docs mark as untested
(``variant``, ``propertyType``, ``page`` of ``/api/cities``) are not sent.
"""

import json
from functools import partial
from typing import TypeVar

from pydantic import BaseModel

from deweloperuch_mcp.client.dto import (
    CitiesDto,
    CityDistrictsDto,
    CityLookupDto,
    InvestmentDto,
    InvestmentSaleEventsDto,
    LocationSearchDto,
    SaleEventsDto,
    validate,
)
from deweloperuch_mcp.client.transport import HttpClient, Reply, build_target, path_segment
from deweloperuch_mcp.errors import UnexpectedResponseError
from deweloperuch_mcp.http_policy import is_html

M = TypeVar("M", bound=BaseModel)

JSON_HEADERS = {"Accept": "application/json"}


def cities(http: HttpClient, query: str, limit: int) -> CitiesDto:
    """``GET /api/cities?q=&limit=`` [P]: cities whose name contains ``query``."""
    return _get(http, build_target("/api/cities", [("q", query), ("limit", limit)]), CitiesDto)


def location_search(http: HttpClient, query: str, limit: int) -> LocationSearchDto:
    """``GET /api/location-search?q=&limit=`` [P]: districts and streets matching ``query``."""
    target = build_target("/api/location-search", [("q", query), ("limit", limit)])
    return _get(http, target, LocationSearchDto)


def city_lookup(http: HttpClient, city: str) -> CityLookupDto:
    """``GET /api/city-lookup?city=`` [P]: a city name or slug -> ``{city, city_slug}``."""
    return _get(http, build_target("/api/city-lookup", [("city", city)]), CityLookupDto)


def city_districts(http: HttpClient, city_slug: str) -> CityDistrictsDto:
    """``GET /api/city-districts?citySlug=`` [P]: districts of a city with counts."""
    target = build_target("/api/city-districts", [("citySlug", city_slug)])
    return _get(http, target, CityDistrictsDto)


def investment(http: HttpClient, slug: str) -> InvestmentDto:
    """``GET /api/map/investments/visible/{slug}`` [P]: an investment with all its offers."""
    return _get(http, f"/api/map/investments/visible/{path_segment(slug)}", InvestmentDto)


def investment_sale_events(http: HttpClient, invest_id: int) -> InvestmentSaleEventsDto:
    """``GET /api/investments/{investId}/sale-events`` [P]: events of every offer."""
    return _get(http, f"/api/investments/{int(invest_id)}/sale-events", InvestmentSaleEventsDto)


def sale_events(http: HttpClient, sale_id: int) -> SaleEventsDto:
    """``GET /api/sale-events?saleId=`` [P]: price events of one offer."""
    return _get(http, build_target("/api/sale-events", [("saleId", int(sale_id))]), SaleEventsDto)


def _get(http: HttpClient, target: str, model: type[M]) -> M:
    return http.get(target, headers=JSON_HEADERS, decode=partial(_decode, model, target))


def _decode(model: type[M], target: str, reply: Reply) -> M:
    path = target.split("?", 1)[0]
    if is_html(reply.headers, reply.body):
        raise UnexpectedResponseError(f"Oczekiwano JSON z {path}, a serwis zwrócił stronę HTML.")
    try:
        data = json.loads(reply.body)
    except (ValueError, RecursionError) as err:
        raise UnexpectedResponseError(f"Odpowiedź {path} nie jest poprawnym JSON: {err}.") from err
    return validate(model, data, path)
