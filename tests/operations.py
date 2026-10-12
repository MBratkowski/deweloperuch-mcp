"""The operations as the interfaces run them: the application's arguments, the session's use
case, the view the CLI prints with ``--json``. For tests of everything below the
interfaces at once (tests/test_services.py, tests/test_links.py)."""

from typing import Any

from deweloperuch_mcp.application import arguments
from deweloperuch_mcp.bootstrap import Session
from deweloperuch_mcp.domain.statistics import DEFAULT_PERIODS
from deweloperuch_mcp.interfaces import views


def search_locations(session: Session, query: object) -> views.LocationSearchResult:
    return views.location_search(session.search_locations(arguments.location_query(query)))


def search_offers(session: Session, city: object, **filters: Any) -> views.OfferSearchResult:
    return views.offer_search(session.search_offers(arguments.offer_search(city, **filters)))


def get_offer(session: Session, offer_id: object, investment_slug: object) -> views.OfferDetail:
    return views.offer_detail(session.get_offer(*arguments.offer(offer_id, investment_slug)))


def get_investment(
    session: Session,
    investment_slug: object,
    *,
    include_history: object = False,
    limit: object = None,
) -> views.Investment:
    given = arguments.investment(investment_slug, include_history=include_history, limit=limit)
    found = session.get_investment(
        given.investment, include_history=given.include_history, limit=given.limit
    )
    return views.investment(found)


def get_government_statistics(
    session: Session, location: object, dataset: object, *, periods: object = DEFAULT_PERIODS
) -> views.GovernmentStatistics:
    found = session.get_government_statistics(
        *arguments.government_statistics(location, dataset, periods=periods)
    )
    return views.government_statistics(found)
