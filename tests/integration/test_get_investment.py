"""``get_investment`` through the session: the real use case and adapters, the service mocked
(respx), no network."""

from typing import Any

import pytest
import respx

from deweloperuch_mcp import bootstrap
from deweloperuch_mcp.errors import InvalidInputError, NotFoundError
from support.providers import operations
from support.providers.routes.investments import (
    investment_routes,
)
from support.providers.service import BASE


def test_get_investment_is_one_request_without_history(
    session: bootstrap.Session, service: respx.MockRouter
) -> None:
    investment, history, _ = investment_routes(service)

    result = operations.get_investment(session, "smolna")

    assert (investment.call_count, history.call_count) == (1, 0)
    assert (result.investment_slug, result.offers_total, len(result.offers)) == ("smolna", 16, 3)
    assert all(offer.price_history is None for offer in result.offers)


def test_get_investment_with_history_and_limit(
    session: bootstrap.Session, service: respx.MockRouter
) -> None:
    investment, history, _ = investment_routes(service)

    result = operations.get_investment(session, "smolna", include_history=True, limit=1)

    assert (investment.call_count, history.call_count) == (1, 1)
    assert [offer.offer_id for offer in result.offers] == [206087]
    assert result.offers_omitted == 2
    assert result.offers[0].price_history is not None
    assert [event.price for event in result.offers[0].price_history] == [1679796.0]


def test_get_investment_unknown_slug_says_where_slugs_come_from(
    session: bootstrap.Session, service: respx.MockRouter
) -> None:
    service.get(BASE + "/api/map/investments/visible/nie-ma").respond(404)

    with pytest.raises(NotFoundError, match="search_offers"):
        operations.get_investment(session, "nie-ma")


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({"investment_slug": "Smolna"}, "investment_slug"),
        ({"investment_slug": "smolna/../x"}, "investment_slug"),
        ({"investment_slug": ""}, "investment_slug"),
        ({"limit": -1}, "limit"),
        ({"limit": 1.5}, "limit"),
        ({"include_history": "yes"}, "include_history"),
    ],
)
def test_get_investment_rejects_bad_input_without_requests(
    session: bootstrap.Session, service: respx.MockRouter, arguments: dict[str, Any], message: str
) -> None:
    arguments = {"investment_slug": "smolna", **arguments}

    with pytest.raises(InvalidInputError, match=message):
        operations.get_investment(session, **arguments)

    assert service.calls.call_count == 0
