"""How the mocked service answers in the golden cases of both consumers: each builder
returns a router setup (``Router``) a case applies before it runs.
"""

from collections.abc import Callable
from typing import Any

import respx

from support.builders.developer_search import developers_found
from support.builders.investment_search import city_with_investments
from support.builders.offers import offers_page
from support.builders.rankings import ranking_with_places
from support.providers.routes.buildings import BUILDING, building_routes
from support.providers.routes.buildings import TREND as BUILDING_TREND
from support.providers.routes.developer_search import developer_search_route
from support.providers.routes.government_statistics import (
    STATS_PATH,
)
from support.providers.routes.investment_search import CITY_INVESTMENTS, investment_search_routes
from support.providers.routes.investments import (
    INVESTMENT,
    investment_routes,
)
from support.providers.routes.offers import offers_route
from support.providers.routes.rankings import ranking_routes
from support.providers.routes.valuation import VALUATION_PATH
from support.providers.samples import body

Router = Callable[[respx.MockRouter], Any]


def locations_with(cities: Any = None, suggestions: Any = None) -> Router:
    def answer(router: respx.MockRouter) -> None:
        router.get(path="/api/cities").respond(200, json=cities or body("api.cities_q"))
        router.get(path="/api/location-search").respond(
            200, json=suggestions or body("api.location_search")
        )

    return answer


NO_CITIES = {"cities": [], "cityMappings": [], "hasMore": False, "total": 0, "page": 1}


FULL_SUGGESTIONS = {"suggestions": [body("api.location_search")["suggestions"][1]] * 6}


def offers_with(page: Any) -> Router:
    return lambda router: offers_route(router, page)


def offers_page_with(total: int, page: int = 1, per_page: int = 10, empty: bool = False) -> Any:
    data = offers_page()
    if empty:
        data["data"] = []
    data["pagination"] = {"page": page, "perPage": per_page, "total": total, "totalPages": 1}
    return data


def offers_answer(status: int, **kw: Any) -> Router:
    return lambda router: router.route(method="GET", path__startswith="/ceny-ofertowe/").respond(
        status, **kw
    )


def investment_answer(status: int, **kw: Any) -> Router:
    return lambda router: router.get(INVESTMENT).respond(status, **kw)


def investment_is(investment: Any) -> Router:
    return lambda router: investment_routes(router, investment)


def many_cities(router: respx.MockRouter) -> None:
    """As many cities as the service ranks (2448 in the sample): its rows and copies."""
    ranking_routes(router, cities=ranking_with_places("api.city_tx_stats", 2448))


def stats_answer(location: str, status: int, **kw: Any) -> Router:
    return lambda router: router.get(path=STATS_PATH + location).respond(status, **kw)


def valuation_answer(status: int, **kw: Any) -> Router:
    return lambda router: router.get(path=VALUATION_PATH).respond(status, **kw)


def without_an_estimate() -> Any:
    answer = body("api.standalone_val")
    answer.update(estimatedValue=None, estimatedPricePerSqm=None, stats=None, transactions=[])
    return answer


def building_answer(status: int, **kw: Any) -> Router:
    return lambda router: router.get(BUILDING).respond(status, **kw)


def trend_answer(status: int, **kw: Any) -> Router:
    def answer(router: respx.MockRouter) -> None:
        building_routes(router)
        router.get(BUILDING_TREND).respond(status, **kw)

    return answer


def search_answer(status: int, **kw: Any) -> Router:
    """The investments of a city answered with ``status`` (for any city)."""
    return lambda router: router.get(path=CITY_INVESTMENTS).respond(status, **kw)


def search_city_is(count: int) -> Router:
    """A city of ``count`` investments (copies of Sopot's two)."""
    return lambda router: investment_search_routes(router, city=city_with_investments(count))


def developers_with(count: int, *, total: int, more: bool) -> Router:
    found = developers_found(count, total=total, more=more)
    return lambda router: developer_search_route(router, found)
