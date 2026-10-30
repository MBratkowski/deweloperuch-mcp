"""Contract of ``deweloperuch_mcp.api.adapters.investments_api`` with the service's real
answers (the samples in docs/discovery/samples/, the raw payloads in tests/fixtures/).
"""

import contextlib
from collections.abc import Callable

import respx

from deweloperuch_mcp.allowlist import match_api, match_dump, match_page
from deweloperuch_mcp.api.adapters.city_sales_api import CitySalesApi
from deweloperuch_mcp.api.adapters.developer_profile_api import (
    DeveloperProfileApi,
)
from deweloperuch_mcp.api.adapters.investments_api import InvestmentsApi
from deweloperuch_mcp.api.adapters.locations_api import LocationsApi
from deweloperuch_mcp.api.adapters.offers_api import OffersApi
from deweloperuch_mcp.api.http.transport import HttpClient
from deweloperuch_mcp.errors import (
    UnexpectedResponseError,
)
from support.builders.offers import offers_list
from support.providers.rsc import (
    offers_payload,
)


def test_every_adapter_requests_a_documented_read_channel(
    http: HttpClient, service: respx.MockRouter
) -> None:
    """D1/D5: each adapter function stays on the read allowlist and off the dumps."""
    service.route(path__startswith="/api/").respond(200, json={})
    calls: list[Callable[[], object]] = [
        lambda: LocationsApi(http).city_search("krak", 8),
        lambda: LocationsApi(http).location_search("mokot", 6),
        lambda: InvestmentsApi(http).visible_investment("smolna"),
        lambda: InvestmentsApi(http).investment_sale_events(33),
        lambda: OffersApi(http).sale_events(2377),
        lambda: offers_list(http, "warszawa", [("page", 2)]),
        lambda: CitySalesApi(http).offer_snapshot("krakow"),
        lambda: DeveloperProfileApi(http).developer_page("polska", "atal"),
    ]
    service.route(path__startswith="/ceny-ofertowe/").respond(200, content=offers_payload({}))

    for call in calls:
        with contextlib.suppress(UnexpectedResponseError):  # bodies are empty: paths matter
            call()

    paths = [call.request.url.path for call in service.calls]
    assert len(paths) == len(calls)
    for path in paths:
        assert match_api(path) is not None or match_page(path) is not None, path
        assert match_dump(path) is None, path
