"""``get_offer`` through the session: the real use case and adapters, the service mocked
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


def test_get_offer_returns_the_offer_with_its_price_history(
    session: bootstrap.Session, service: respx.MockRouter
) -> None:
    investment, history, events = investment_routes(service)

    result = operations.get_offer(session, 2377, "smolna")

    assert (investment.call_count, events.call_count, history.call_count) == (1, 1, 0)
    assert (result.offer_id, result.name, result.investment_slug) == (2377, "C224", "smolna")
    assert (result.price, result.area_m2, result.status) == (1620175.0, 69.5, "active")
    assert [(e.kind, e.price) for e in result.price_history] == [
        ("offer", 1620000.0),
        ("archived", 1620000.0),
        ("restored", 1620175.0),
    ]


def test_get_offer_missing_from_the_investment_is_not_found(
    session: bootstrap.Session, service: respx.MockRouter
) -> None:
    _, _, events = investment_routes(service)

    with pytest.raises(NotFoundError, match="999") as caught:
        operations.get_offer(session, 999, "smolna")

    assert "get_investment" in str(caught.value)
    assert events.call_count == 0


def test_get_offer_after_get_investment_reuses_the_cached_investment(
    session: bootstrap.Session, service: respx.MockRouter
) -> None:
    investment, _, _ = investment_routes(service)

    operations.get_investment(session, "smolna")
    operations.get_offer(session, 2377, "smolna")

    assert investment.call_count == 1


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        ({"offer_id": 0}, "offer_id"),
        ({"offer_id": -5}, "offer_id"),
        ({"offer_id": "2377"}, "offer_id"),
        ({"offer_id": True}, "offer_id"),
        ({"investment_slug": "SMOLNA"}, "investment_slug"),
    ],
)
def test_get_offer_rejects_bad_input_without_requests(
    session: bootstrap.Session, service: respx.MockRouter, arguments: dict[str, Any], message: str
) -> None:
    arguments = {"offer_id": 2377, "investment_slug": "smolna", **arguments}

    with pytest.raises(InvalidInputError, match=message):
        operations.get_offer(session, **arguments)

    assert service.calls.call_count == 0
