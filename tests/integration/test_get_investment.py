"""``get_investment`` through the session: the real use case and adapters, the service mocked
(respx), no network."""

import datetime as dt
from typing import Any

import httpx
import pytest
import respx

from deweloperuch_mcp import bootstrap
from deweloperuch_mcp.consumers.shared.offer_views import PriceEventView
from deweloperuch_mcp.errors import InvalidInputError, NotFoundError, UnexpectedResponseError
from support.providers import operations
from support.providers.error_answers import unknown_entity
from support.providers.routes.investments import (
    INVESTMENT,
    SMOLNA_2026_10_31,
    investment_routes,
    smolna_with_events,
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
    """[P 2026-10-30] the 2.0 answer carries the events: one request for both."""
    investment, history, _ = investment_routes(service, smolna_with_events())

    result = operations.get_investment(session, "smolna", include_history=True, limit=2)

    assert (investment.call_count, history.call_count) == (1, 0)
    assert [offer.offer_id for offer in result.offers] == [206523, 206087]
    assert result.offers_omitted == 15
    assert [offer.price_history for offer in result.offers] == [
        [PriceEventView(date=dt.date(2026, 10, 24), kind="offer", price=3735107.0)],
        [PriceEventView(date=dt.date(2026, 10, 3), kind="offer", price=1679796.0)],
    ]


def test_get_investment_history_off_the_contract_leaves_the_investment_readable(
    session: bootstrap.Session, service: respx.MockRouter
) -> None:
    """The answer of 2026-10-09 (the sample) has no price events: the history is off the
    contract (exit 6, D21), the investment without it still reads, nothing else is asked."""
    investment, history, _ = investment_routes(service)

    with pytest.raises(UnexpectedResponseError, match="bez include_history") as caught:
        operations.get_investment(session, "smolna", include_history=True)
    result = operations.get_investment(session, "smolna")

    assert caught.value.detail is not None and "sale.0.ev: Field required" in caught.value.detail
    assert len(result.offers) == 3
    assert (investment.call_count, history.call_count) == (1, 0)  # once, then the cache


def test_get_investment_with_an_unknown_event_type_fails_the_history(
    session: bootstrap.Session, service: respx.MockRouter
) -> None:
    """A type index outside the client's table: the positions may mean something else
    now, so no event is shown as another one (D21)."""
    answer = smolna_with_events()
    answer["sale"][2]["ev"][1][2] = 3  # offer 2377, its withdrawal [.., 1, 5] -> [.., 3, 5]
    investment_routes(service, answer)

    with pytest.raises(UnexpectedResponseError, match="^Historia cen inwestycji") as caught:
        operations.get_investment(session, "smolna", include_history=True, limit=1)

    assert caught.value.detail == (
        "/api/map/investments/visible/smolna: sale.2.ev.1.event_type: Value error, nieznany "
        "numer typu zdarzenia 3"
    )


def test_histories_of_another_answer_than_the_offers_fail_closed(
    session: bootstrap.Session, service: respx.MockRouter
) -> None:
    """An answer the cache may not keep (``no-store``; the route sends cacheable headers
    [P 2026-10-30]) is read twice, and the second may be another state of the investment:
    an offer of the first answer missing from the second gets no made-up empty history."""
    later = smolna_with_events()
    later["sale"] = [sale for sale in later["sale"] if sale["sale_id"] != 206523]
    no_store = {"Cache-Control": "no-store"}
    route = service.get(INVESTMENT).mock(
        side_effect=[
            httpx.Response(200, content=SMOLNA_2026_10_31.read_bytes(), headers=no_store),
            httpx.Response(200, json=later, headers=no_store),
        ]
    )

    with pytest.raises(UnexpectedResponseError, match="nie mają historii części ofert") as caught:
        operations.get_investment(session, "smolna", include_history=True, limit=2)

    assert route.call_count == 2
    assert caught.value.detail == "brak historii ofert 206523"
    assert "get_offer" in str(caught.value)


def test_get_investment_unknown_slug_says_where_slugs_come_from(
    session: bootstrap.Session, service: respx.MockRouter
) -> None:
    # [P 2026-10-30] docs/discovery/endpoints.md section 9: an unknown slug.
    service.get(BASE + "/api/map/investments/visible/nie-ma").respond(404, **unknown_entity())

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
