"""``InvestmentSearchApi``: investments as the service lists them for a search, the
``InvestmentDirectory`` port (D1: JSON API).

- The investments of a city: ``GET /api/map/investments?citySlug=`` [P] (sample
  ``api.map_investments_sopot``), the list of the city's map at once, without pagination.
  Sent with ``citySlug`` only: the other query parameters the UI sends (``developer``,
  ``price``, ``includeArchived``...) are [P z kodu] and untested on the server, so the
  domain filters, orders and cuts the list. Without ``includeArchived=true`` investments
  without active offers may be missing [W].
- Investments by a part of the name, across the country: ``GET /api/investments?q=&limit=``
  [P] (sample ``api.investments_q``), without ``page`` (untested for this endpoint).
"""

from deweloperuch_mcp.api.dto.city_investments_dto import CityInvestmentsDto
from deweloperuch_mcp.api.dto.named_investments_dto import NamedInvestmentsDto
from deweloperuch_mcp.api.http.json_endpoint import JsonEndpoint
from deweloperuch_mcp.api.http.transport import HttpClient
from deweloperuch_mcp.models.investment_summary import (
    InvestmentMatches,
    InvestmentName,
    InvestmentsLimit,
    InvestmentSummary,
)
from deweloperuch_mcp.models.values import CitySlug


class InvestmentSearchApi:
    """``usecases.ports.InvestmentDirectory`` of the service; ``city_investments`` and
    ``named_investments`` are its resources as the service sends them (DTOs)."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def in_city(self, city: CitySlug) -> tuple[InvestmentSummary, ...]:
        # [W] samples api.map_investments_sopot and api.city_sales_sopot (both 2026-10-09):
        # the list holds every investment with active offers (Sopot's two are those of
        # the dump of its active offers); without `includeArchived=true` (not sent) those
        # without active offers may be missing.
        return self.city_investments(city.value).to_model()

    def by_name(self, name: InvestmentName, limit: InvestmentsLimit) -> InvestmentMatches:
        # [W] sample api.investments_q (limit=5): another `limit` is honoured
        # (tests/e2e/test_live_investment_search.py checks it).
        return self.named_investments(name.text, limit.value).to_model()

    def city_investments(self, city_slug: str) -> CityInvestmentsDto:
        """``GET /api/map/investments?citySlug=`` [P]: every investment of a city."""
        target = HttpClient.target("/api/map/investments", [("citySlug", city_slug)])
        return JsonEndpoint(self._http, target).get(CityInvestmentsDto)

    def named_investments(self, query: str, limit: int) -> NamedInvestmentsDto:
        """``GET /api/investments?q=&limit=`` [P]: investments whose name contains ``query``."""
        target = HttpClient.target("/api/investments", [("q", query), ("limit", limit)])
        return JsonEndpoint(self._http, target).get(NamedInvestmentsDto)
