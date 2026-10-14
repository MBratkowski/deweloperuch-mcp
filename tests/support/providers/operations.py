"""The operations as the interfaces run them: the application's arguments, the session's use
case, the view the CLI prints with ``--json``. For tests of everything below the
interfaces at once (tests/integration/)."""

from typing import Any

from deweloperuch_mcp.bootstrap import Session
from deweloperuch_mcp.consumers.shared.government_statistics_views import (
    GovernmentStatisticsView,
)
from deweloperuch_mcp.consumers.shared.investment_views import InvestmentView
from deweloperuch_mcp.consumers.shared.location_views import LocationSearchView
from deweloperuch_mcp.consumers.shared.offer_views import OfferDetailView, OfferSearchView
from deweloperuch_mcp.models.government_statistics import DEFAULT_PERIODS
from deweloperuch_mcp.usecases.get_government_statistics import GetGovernmentStatisticsRequest
from deweloperuch_mcp.usecases.get_investment import GetInvestmentRequest
from deweloperuch_mcp.usecases.get_offer import GetOfferRequest
from deweloperuch_mcp.usecases.search_locations import SearchLocationsRequest
from deweloperuch_mcp.usecases.search_offers import SearchOffersRequest


def search_locations(session: Session, query: object) -> LocationSearchView:
    request = SearchLocationsRequest.parse(query=query)
    return LocationSearchView.from_result(session.search_locations.execute(request))


def search_offers(session: Session, city: object, **filters: Any) -> OfferSearchView:
    request = SearchOffersRequest.parse(city=city, **filters)
    return OfferSearchView.from_result(session.search_offers.execute(request))


def get_offer(session: Session, offer_id: object, investment_slug: object) -> OfferDetailView:
    request = GetOfferRequest.parse(offer_id=offer_id, investment_slug=investment_slug)
    return OfferDetailView.from_result(session.get_offer.execute(request))


def get_investment(
    session: Session,
    investment_slug: object,
    *,
    include_history: object = False,
    limit: object = None,
) -> InvestmentView:
    request = GetInvestmentRequest.parse(
        investment_slug=investment_slug, include_history=include_history, limit=limit
    )
    return InvestmentView.from_result(session.get_investment.execute(request))


def get_government_statistics(
    session: Session, location: object, dataset: object, *, periods: object = DEFAULT_PERIODS
) -> GovernmentStatisticsView:
    request = GetGovernmentStatisticsRequest.parse(
        location=location, dataset=dataset, periods=periods
    )
    return GovernmentStatisticsView.from_result(session.get_government_statistics.execute(request))
