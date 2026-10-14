"""``search_developers`` through the session: the real use case and adapters, the service mocked
(respx), no network."""

from pathlib import Path
from typing import Any

import respx

from deweloperuch_mcp import bootstrap
from deweloperuch_mcp.consumers.shared.developer_views import (
    DeveloperMatchView,
    DeveloperSearchView,
)
from deweloperuch_mcp.models.developer_match import (
    DEFAULT_MATCHES,
)
from deweloperuch_mcp.throttle import RequestLimiter
from deweloperuch_mcp.usecases.search_developers import SearchDevelopersRequest
from support.builders.developer_search import PROFILES
from support.providers.routes.developer_search import developer_search_route


def search(session: bootstrap.Session, name: object, limit: object = DEFAULT_MATCHES) -> Any:
    found = session.search_developers.execute(SearchDevelopersRequest.parse(name=name, limit=limit))
    return DeveloperSearchView.from_result(found)


def test_the_session_searches_developers(tmp_path: Path, service: respx.MockRouter) -> None:
    developer_search_route(service)
    limiter = RequestLimiter(tmp_path, min_interval=0, testing_only_allow_fast_interval=True)

    with bootstrap.Session(limiter=limiter) as session:
        result = search(session, "atal")

    assert result == DeveloperSearchView(
        total=1,
        returned=1,
        truncated=False,
        hint=None,
        items=[
            DeveloperMatchView(
                developer_slug="atal",
                name="ATAL S.A.",
                offer_count=4265,
                developer_url=PROFILES + "atal",
            )
        ],
    )
