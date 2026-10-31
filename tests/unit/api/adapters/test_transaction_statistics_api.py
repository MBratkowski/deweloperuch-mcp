"""Tests of ``deweloperuch_mcp.api.adapters.transaction_statistics_api``."""

from typing import Any

import httpx
import pytest
import respx

from deweloperuch_mcp.api.adapters.transaction_statistics_api import TransactionStatisticsApi
from deweloperuch_mcp.api.dto.transaction_stats_page_dto import OTHER_MARKET
from deweloperuch_mcp.api.http.transport import HttpClient
from deweloperuch_mcp.models.errors import (
    SERVICE_CHANGED,
    NotFoundError,
    UnexpectedResponseError,
)
from deweloperuch_mcp.models.transaction_series import (
    Granularity,
    TransactionCity,
    TransactionPeriod,
    TransactionSeries,
)
from support.builders.transactions import (
    month_rows,
    page_with_months,
    warszawa_page,
    zero_month,
)
from support.providers.error_answers import (
    CHANGED_SERVICE,
    UNKNOWN_CITY_ERROR,
    removed_route,
    unknown_entity,
    unknown_location_page,
)
from support.providers.routes.offers import RSC_HEADERS
from support.providers.routes.transactions import (
    CITY_TREND,
    STATS_PAGE,
    STATS_PAGE_WARSZAWA,
    TREND_PATH,
)
from support.providers.rsc import OFFERS_WARSZAWA_20261031, raw
from support.providers.samples import body


def read(http: HttpClient, granularity: Granularity, city: str = "warszawa") -> TransactionSeries:
    return TransactionStatisticsApi(http).transaction_series(TransactionCity(city), granularity)


def page_route(service: respx.MockRouter, page: bytes) -> respx.Route:
    return service.get(path__regex=STATS_PAGE).respond(200, content=page, headers=RSC_HEADERS)


def test_months_are_read_from_the_statistics_page_of_the_city(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """[P 2026-10-31] tests/fixtures/rsc/stats_tx_warszawa_20261031.rsc: the prop ``view``,
    118 months from 2017-01; the three newest are the page's empty padding, so the series
    ends with 2026-07, the newest month with transactions, and keeps the empty 2026-06."""
    route = page_route(service, warszawa_page())

    found = read(http, Granularity.MONTH)

    assert route.call_count == 1
    request = route.calls.last.request
    assert str(request.url) == STATS_PAGE_WARSZAWA
    assert request.headers["rsc"] == "1"
    assert found.granularity is Granularity.MONTH
    assert (len(found.periods), found.periods[0].period) == (115, "2017-01")
    assert found.periods[0] == TransactionPeriod(
        period="2017-01",
        transactions=890,
        median_price_per_m2=7656.0,
        average_price_per_m2=7903.0,
        median_area_m2=47.9,
        average_area_m2=53.3,
        median_price=355000.0,
        average_price=423836.0,
    )
    assert (found.periods[-1].period, found.periods[-1].transactions) == ("2026-07", 35)
    assert found.periods[-2] == TransactionPeriod("2026-06", 0)


def test_quarters_are_read_from_the_sample_with_its_request(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """[P 2026-10-30] the trend's ``avgPriceSqm`` is the median price of one m²."""
    route = service.get(CITY_TREND).respond(200, json=body("api.avg_trend_city"))

    found = read(http, Granularity.QUARTER)

    assert route.call_count == 1
    assert found.periods == (
        TransactionPeriod("2017-Q1", 2922, median_price_per_m2=7595.0),
        TransactionPeriod("2017-Q2", 2854, median_price_per_m2=7695.0),
        TransactionPeriod("2017-Q3", 2893, median_price_per_m2=7844.0),
    )


def test_the_city_goes_into_the_path(http: HttpClient, service: respx.MockRouter) -> None:
    page = service.get(path="/statystyki/krakow/transakcje").respond(
        200, content=warszawa_page(), headers=RSC_HEADERS
    )
    trend = service.get(path=TREND_PATH + "krakow").respond(200, json=body("api.avg_trend_city"))

    read(http, Granularity.MONTH, "krakow")
    read(http, Granularity.QUARTER, "krakow")

    assert page.calls.last.request.url.raw_path.decode() == "/statystyki/krakow/transakcje?_rsc="
    assert trend.call_count == 1


def test_a_repeat_comes_from_the_cache(http: HttpClient, service: respx.MockRouter) -> None:
    route = page_route(service, warszawa_page())

    assert read(http, Granularity.MONTH) == read(http, Granularity.MONTH)
    assert route.call_count == 1


def test_a_month_without_transactions_has_no_prices_nor_areas(
    http: HttpClient, service: respx.MockRouter
) -> None:
    first, _, third = month_rows(3)
    page_route(service, page_with_months([first, zero_month("2017-02"), third]))

    found = read(http, Granularity.MONTH).periods

    assert found[1] == TransactionPeriod("2017-02", 0)
    assert found[1].measures == (None,) * 6
    assert found[0].median_price_per_m2 == 7656.0  # the others keep theirs


def test_a_quarter_without_transactions_has_no_price(
    http: HttpClient, service: respx.MockRouter
) -> None:
    # The same zeros as the months show live, in the shape of the quarterly sample.
    data = body("api.avg_trend_city")
    data["data"][2].update(count=0, avgPriceSqm=0)
    service.get(CITY_TREND).respond(200, json=data)

    found = read(http, Granularity.QUARTER).periods

    assert found[2] == TransactionPeriod("2017-Q3", 0)


@pytest.mark.parametrize(
    "zeros", [{"med_amount": 0}, {"med_size": "0"}, {"avg_price_sqm": 0.0, "avg_size": ""}]
)
def test_a_zero_price_or_area_is_a_missing_value(
    http: HttpClient, service: respx.MockRouter, zeros: dict[str, Any]
) -> None:
    rows = month_rows(1)
    rows[0].update(zeros)
    page_route(service, page_with_months(rows))

    first = read(http, Granularity.MONTH).periods[0]

    assert first.transactions == 890
    assert sum(value is None for value in first.measures) == len(zeros)


def test_numbers_as_text_and_missing_measures_are_tolerated(
    http: HttpClient, service: respx.MockRouter
) -> None:
    rows = month_rows(1)
    rows[0].update(med_price_sqm="7656", med_size=None, med_amount="")
    page_route(service, page_with_months(rows))

    first = read(http, Granularity.MONTH).periods[0]

    assert (first.median_price_per_m2, first.median_area_m2, first.median_price) == (
        7656.0,
        None,
        None,
    )


def test_periods_in_another_order_are_sorted(http: HttpClient, service: respx.MockRouter) -> None:
    page_route(service, page_with_months(month_rows(3)[::-1]))

    found = read(http, Granularity.MONTH)

    assert [item.period for item in found.periods] == ["2017-01", "2017-02", "2017-03"]


def test_a_page_without_any_transaction_is_a_series_without_periods(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """Only the page's padding: no month to show (the domain reports a city without data)."""
    page_route(service, page_with_months([zero_month("2017-01"), zero_month("2017-02")]))

    assert read(http, Granularity.MONTH).periods == ()


@pytest.mark.parametrize("granularity", list(Granularity))
def test_an_empty_list_is_a_series_without_periods(
    http: HttpClient, service: respx.MockRouter, granularity: Granularity
) -> None:
    page_route(service, page_with_months([]))
    service.get(CITY_TREND).respond(200, json={"data": [], "scope": "city", "scopeName": None})

    assert read(http, granularity).periods == ()


@pytest.mark.parametrize(
    ("change", "detail"),
    [
        (lambda rows: rows.append(dict(rows[0])), "powtarzają"),
        (lambda rows: rows[0].update(transaction_count=-1, secondary_count=-1), "ujemna"),
    ],
)
def test_inconsistent_periods_mean_the_service_changed(
    http: HttpClient, service: respx.MockRouter, change: Any, detail: str
) -> None:
    rows = month_rows(3)
    change(rows)
    page_route(service, page_with_months(rows))

    with pytest.raises(UnexpectedResponseError) as caught:
        read(http, Granularity.MONTH)

    assert SERVICE_CHANGED in str(caught.value)
    assert caught.value.detail is not None and detail in caught.value.detail


def test_a_month_of_another_market_is_refused_with_its_own_message(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """The months are described as the secondary market: a month that is not all of it
    is another series, refused with its own message, not as a changed service."""
    rows = month_rows(3)
    rows[1]["secondary_count"] = 800  # of 880
    page_route(service, page_with_months(rows))

    with pytest.raises(UnexpectedResponseError) as caught:
        read(http, Granularity.MONTH)

    assert str(caught.value) == OTHER_MARKET
    assert (
        caught.value.detail == "prop view, miesiąc 2017-02: 800 z 880 transakcji z rynku wtórnego"
    )


@pytest.mark.parametrize(
    "refused",
    [
        page_with_months([{**month_rows(1)[0], "month": "2017-1"}]),  # off the contract
        page_with_months([{**month_rows(1)[0], "secondary_count": 1}]),  # another market
    ],
)
def test_a_refused_page_is_not_kept_in_the_cache(
    http: HttpClient, service: respx.MockRouter, refused: bytes
) -> None:
    """The page is checked while the transport reads it, so a refused body is never cached:
    the next read asks again (a page fixed meanwhile gives its months)."""
    route = service.get(path__regex=STATS_PAGE).mock(
        side_effect=[
            httpx.Response(200, content=refused, headers=RSC_HEADERS),
            httpx.Response(200, content=warszawa_page(), headers=RSC_HEADERS),
        ]
    )

    with pytest.raises(UnexpectedResponseError):
        read(http, Granularity.MONTH)
    found = read(http, Granularity.MONTH)

    assert route.call_count == 2
    assert found.periods[-1].period == "2026-07"


@pytest.mark.parametrize(
    "answer",
    [
        {"json": {"data": [{"period": "2017-1", "avgPriceSqm": 1, "count": 1}]}},
        {"json": {"rows": []}},
        {"json": [1, 2]},
        {"text": "<html>nie</html>", "headers": {"Content-Type": "text/html"}},
        {"content": b"{", "headers": {"Content-Type": "application/json"}},
    ],
)
def test_a_trend_off_the_contract_is_an_unexpected_response(
    http: HttpClient, service: respx.MockRouter, answer: dict[str, Any]
) -> None:
    service.get(CITY_TREND).respond(200, **answer)

    with pytest.raises(UnexpectedResponseError):
        read(http, Granularity.QUARTER)


@pytest.mark.parametrize(
    "page",
    [
        raw(OFFERS_WARSZAWA_20261031),  # another page: no prop view
        page_with_months([{**month_rows(1)[0], "month": "2017-1"}]),
        page_with_months([{"month": "2017-01"}]),
    ],
)
def test_a_page_off_the_contract_is_an_unexpected_response(
    http: HttpClient, service: respx.MockRouter, page: bytes
) -> None:
    page_route(service, page)

    with pytest.raises(UnexpectedResponseError) as caught:
        read(http, Granularity.MONTH)

    assert str(caught.value).endswith(SERVICE_CHANGED)


def test_a_view_without_months_is_an_unexpected_response(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """The prop is there, its months are not (a shape: the rest of the real page)."""
    page = warszawa_page().replace(b'"view":{"monthly":', b'"view":{"months":', 1)
    page_route(service, page)

    with pytest.raises(UnexpectedResponseError) as caught:
        read(http, Granularity.MONTH)

    assert (caught.value.detail or "").startswith(
        "/statystyki/warszawa/transakcje (prop view): monthly: "
    )


def test_an_unknown_city_is_not_found_on_both_channels(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """[P 2026-10-31] the page answers a city it does not know with a 404 whose body is a
    flight stream; [P 2026-10-30] the trend with a JSON 404 ``{"error": "Unknown city"}``."""
    service.get(path__regex=STATS_PAGE).respond(404, **unknown_location_page())
    service.route(method="GET", path__startswith=TREND_PATH).respond(
        404, **unknown_entity(UNKNOWN_CITY_ERROR)
    )

    for granularity in Granularity:
        with pytest.raises(NotFoundError) as caught:
            read(http, granularity, "nieistniejace-miasto")
        assert "Unknown" not in str(caught.value)


@pytest.mark.parametrize(
    "answer",
    [
        {"status_code": 404, **removed_route()},
        {"status_code": 308, "headers": {"Location": "/statystyki/warszawa"}},
        {"status_code": 410, **removed_route()},
    ],
)
def test_a_removed_or_moved_page_means_the_service_changed(
    http: HttpClient, service: respx.MockRouter, answer: dict[str, Any]
) -> None:
    """D21: a page that is gone (an HTML 404, a 410) or moved (a redirect) is a changed
    service, never an unknown city."""
    rest = dict(answer)
    service.get(path__regex=STATS_PAGE).respond(rest.pop("status_code"), **rest)

    with pytest.raises(UnexpectedResponseError) as caught:
        read(http, Granularity.MONTH)

    assert str(caught.value) == CHANGED_SERVICE
