"""Tests of ``deweloperuch_mcp.api.http.rsc_page``: ``RscPage.props``, several props of one
page in one request, on the raw 2.0 payloads of 2026-10-31 (tests/fixtures/rsc/README.md)."""

from pathlib import Path

import pytest
import respx
from pydantic import BaseModel

from deweloperuch_mcp.api.http.rsc_page import RscPage
from deweloperuch_mcp.api.http.transport import HttpClient
from deweloperuch_mcp.errors import SERVICE_CHANGED, NotFoundError, UnexpectedResponseError
from support.providers.error_answers import (
    CHANGED_SERVICE,
    removed_route,
    unknown_location_page,
)
from support.providers.rsc import (
    DEVELOPER_UNKNOWN,
    DEVELOPER_WARSZAWA_20261031,
    OFFERS_UNKNOWN_CITY_20261031,
    OFFERS_WARSZAWA_20261031,
    STATS_TX_KARPACZ_20261031,
    STATS_TX_WARSZAWA_20261031,
    raw,
)

RSC = {"Content-Type": "text/x-component"}

# A test of the shape: two client elements share prop names, the first with a plain value,
# a reference, `$undefined`, null, 0 and a slug, the second with an object, an empty list
# (a filter without results) and the same slug again.
SHAPES = (
    b'0:["$","$L1",null,{"title":"Strona","rows":"$2:props:rows","note":"$undefined",'
    b'"city":null,"total":0,"slug":"atal"}]\n'
    b'2:["$","$L1",null,{"title":{"text":"Strona"},"rows":[],"summary":"tekst","slug":"atal"}]\n'
)

# Two client elements that give one name two different plain values.
AMBIGUOUS = (
    b'0:["$","$L1",null,{"metric":"tx-m2","rows":[1]}]\n2:["$","$L1",null,{"metric":"tx-cena"}]\n'
)


def page_of(service: respx.MockRouter, path: str, fixture: Path | bytes) -> respx.Route:
    """``path`` answered with a payload as the service sends it."""
    content = fixture if isinstance(fixture, bytes) else raw(fixture)
    return service.get(path=path).respond(200, content=content, headers=RSC)


def test_several_props_of_one_page_come_from_one_request(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """The offer list needs its rows (a list) and its paging (an object)."""
    route = page_of(service, "/ceny-ofertowe/warszawa/mieszkania", OFFERS_WARSZAWA_20261031)

    found = RscPage(http, "/ceny-ofertowe/warszawa/mieszkania").props(
        ("sales", "serverPaginationData")
    )

    assert len(found["sales"]) == 25
    assert found["serverPaginationData"]["totalCount"] == 11672
    assert route.call_count == 1
    assert (
        route.calls.last.request.url.raw_path.decode() == "/ceny-ofertowe/warszawa/mieszkania?_rsc="
    )
    assert route.calls.last.request.headers["rsc"] == "1"


def test_the_props_of_a_nested_client_element_are_read_and_so_are_plain_values(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """The developer page keeps its data in the ``hero`` element, which sits in the props
    of another client element: ``component_props`` reaches it (pinned in test_flight.py).
    Three of the props are plain values, read because the page has no object or list
    under their names; ``investments`` is a list first and a ``$…`` reference later."""
    path = "/ceny-ofertowe/warszawa/deweloperzy/atal"
    page_of(service, path, DEVELOPER_WARSZAWA_20261031)

    found = RscPage(http, path).props(
        ("investments", "developerSlug", "developerName", "developerId", "spec")
    )

    assert len(found["investments"]) == 4
    assert (found["developerSlug"], found["developerName"], found["developerId"]) == (
        "atal",
        "ATAL S.A.",
        43,
    )
    assert found["spec"]["id"] == "ceny-w-miastach"  # the first of four: the cities


def test_the_transaction_statistics_of_a_city(http: HttpClient, service: respx.MockRouter) -> None:
    page_of(service, "/statystyki/warszawa/transakcje", STATS_TX_WARSZAWA_20261031)

    found = RscPage(http, "/statystyki/warszawa/transakcje").props(("view",), ("latestSummary",))

    assert len(found["view"]["monthly"]) == 118
    assert found["latestSummary"]["month"] == "2026-04"


def test_an_optional_prop_that_is_null_is_none(http: HttpClient, service: respx.MockRouter) -> None:
    """[P 2026-10-31] a small town's page has ``latestSummary: null``."""
    page_of(service, "/statystyki/karpacz/transakcje", STATS_TX_KARPACZ_20261031)

    found = RscPage(http, "/statystyki/karpacz/transakcje").props(("view",), ("latestSummary",))

    assert len(found["view"]["monthly"]) == 118
    assert found["latestSummary"] is None


def test_an_optional_prop_that_is_absent_is_none(
    http: HttpClient, service: respx.MockRouter
) -> None:
    page_of(service, "/ceny-ofertowe/warszawa/mieszkania", OFFERS_WARSZAWA_20261031)

    found = RscPage(http, "/ceny-ofertowe/warszawa/mieszkania").props(("sales",), ("initialData",))

    assert found["initialData"] is None and len(found["sales"]) == 25


def test_a_required_prop_that_is_null_is_a_changed_page(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """Required means the data is there: a ``null`` is not data, and the page has no 404
    marker, so the page does not match the contract."""
    page_of(service, "/statystyki/karpacz/transakcje", STATS_TX_KARPACZ_20261031)

    with pytest.raises(UnexpectedResponseError) as caught:
        RscPage(http, "/statystyki/karpacz/transakcje").props(("view", "latestSummary"))

    assert str(caught.value).endswith(SERVICE_CHANGED)
    detail = caught.value.detail or ""
    assert detail.startswith("/statystyki/karpacz/transakcje nie zawiera danych w propsie")
    assert "'latestSummary'" in detail and "'view'" not in detail.split("(")[0]


def test_required_props_that_are_absent_are_named_in_the_detail(
    http: HttpClient, service: respx.MockRouter
) -> None:
    page_of(service, "/ceny-ofertowe/warszawa/mieszkania", OFFERS_WARSZAWA_20261031)

    with pytest.raises(UnexpectedResponseError) as caught:
        RscPage(http, "/ceny-ofertowe/warszawa/mieszkania").props(
            ("sales", "initialData", "initialApiParams")
        )

    assert (caught.value.detail or "").startswith(
        "/ceny-ofertowe/warszawa/mieszkania nie zawiera danych w propsach 'initialData', "
        "'initialApiParams' (propsy z danymi: "
    )


def test_a_page_with_the_404_marker_is_not_found(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """[P 2026-10-31] an unknown city: 200, no rows, Next.js's 404 digest."""
    path = "/ceny-ofertowe/nieistniejace-miasto/mieszkania"
    page_of(service, path, OFFERS_UNKNOWN_CITY_20261031)

    with pytest.raises(NotFoundError) as caught:
        RscPage(http, path).props(("sales", "serverPaginationData"))

    assert caught.value.detail == (
        f"{path}: brak propsów 'sales', 'serverPaginationData', strona zgłasza "
        "NEXT_HTTP_ERROR_FALLBACK;404"
    )


def test_a_page_with_the_heading_of_a_missing_entity_is_not_found(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """The ``missing`` heading, as ``prop`` reads it (the 1.0 page of an unknown developer)."""
    path = "/ceny-ofertowe/warszawa/deweloperzy/nieistniejacy-deweloper"
    page_of(service, path, DEVELOPER_UNKNOWN)

    with pytest.raises(NotFoundError) as caught:
        RscPage(http, path).props(("investments",), missing="Deweloper nie znaleziony")

    assert caught.value.detail == (
        f"{path}: brak propsa 'investments', strona ma nagłówek 'Deweloper nie znaleziony'"
    )


def test_references_and_nulls_are_not_values_and_objects_come_first(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """A ``$`` reference of the stream (``$2:props:rows``, ``$undefined``) and ``null`` are
    no values; an object or a list wins over a plain value of the same name, which counts
    only where the page has neither (``summary``). Present means "not null": an empty list
    (a filter without results) and 0 are data, never missing data; a plain value repeated
    unchanged is one value."""
    page_of(service, "/ceny-ofertowe/sopot/mieszkania", SHAPES)

    found = RscPage(http, "/ceny-ofertowe/sopot/mieszkania").props(
        ("title", "rows", "summary", "total", "slug"), ("note", "city")
    )

    assert found == {
        "title": {"text": "Strona"},
        "rows": [],
        "summary": "tekst",
        "total": 0,
        "slug": "atal",
        "note": None,
        "city": None,
    }


def test_different_plain_values_of_one_name_are_a_changed_page(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """Without an object or a list under the name, two different plain values leave no one
    value to read: the page does not give it any more (the name is in the detail)."""
    page_of(service, "/statystyki/karpacz/transakcje", AMBIGUOUS)

    with pytest.raises(UnexpectedResponseError) as caught:
        RscPage(http, "/statystyki/karpacz/transakcje").props(("rows",), ("metric",))

    assert str(caught.value).endswith(SERVICE_CHANGED)
    assert "'metric'" in (caught.value.detail or "")
    assert "tx-cena" not in str(caught.value)


@pytest.mark.parametrize(
    ("fixture", "path", "name"),
    [
        # [P 2026-10-31] the chart switch of a small town: tx-m2, tx-cena, tx-rr, tx-m2
        (STATS_TX_KARPACZ_20261031, "/statystyki/karpacz/transakcje", "metric"),
        # the headings of the page's sections: Przegląd, Dzielnice
        (STATS_TX_WARSZAWA_20261031, "/statystyki/warszawa/transakcje", "title"),
    ],
)
def test_a_name_with_different_plain_values_on_a_real_page_is_refused(
    http: HttpClient, service: respx.MockRouter, fixture: Path, path: str, name: str
) -> None:
    page_of(service, path, fixture)

    with pytest.raises(UnexpectedResponseError) as caught:
        RscPage(http, path).props(("view",), (name,))

    assert f"{name!r}" in (caught.value.detail or "")


def test_a_404_page_is_a_changed_service_unless_the_route_opts_in(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """D21: the offer lists and the developer page answer what they do not know with a 200
    and the 404 marker [P 2026-10-31], so a 404 there, even a flight stream, means the
    route is gone or was rebuilt, never an unknown city."""
    path = "/ceny-ofertowe/nieistniejace-miasto/mieszkania"
    service.get(path=path).respond(404, **unknown_location_page())

    with pytest.raises(UnexpectedResponseError) as listed:
        RscPage(http, path).props(("sales",))
    with pytest.raises(UnexpectedResponseError) as one:
        RscPage(http, path).prop("serverPaginationData", BaseModel)

    assert str(listed.value) == str(one.value) == CHANGED_SERVICE


def test_a_route_that_opts_in_reads_its_own_404_as_unknown_data(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """[P 2026-10-31] the statistics pages answer an unknown location with a 404 whose body
    is a flight stream (endpoints.md section 9, "Pages"): their adapters opt in."""
    path = "/statystyki/nieistniejace-miasto/dane-rzadowe"
    service.get(path=path).respond(404, **unknown_location_page())

    with pytest.raises(NotFoundError) as caught:
        RscPage(http, path, unknown_404=True).props(("blocks",))

    assert caught.value.detail == f"{path}?_rsc=: HTTP 404, text/x-component"


def test_a_removed_route_stays_a_changed_service_also_where_404_is_opted_in(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """The Next.js HTML not-found page is no answer of the route itself (D21)."""
    path = "/statystyki/nieistniejace-miasto/dane-rzadowe"
    service.get(path=path).respond(404, **removed_route())

    with pytest.raises(UnexpectedResponseError) as caught:
        RscPage(http, path, unknown_404=True).props(("blocks",))

    assert str(caught.value) == CHANGED_SERVICE
