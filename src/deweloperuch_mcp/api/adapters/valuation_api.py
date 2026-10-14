"""``ValuationApi``: valuations of flats by the service, the ``ValuationSource`` port.

- a valuation: ``GET /api/standalone-valuation?area=&lat=&lng=[&address=]`` [P], the
  address from ``ValuationQuery``; one request per valuation.
"""

from deweloperuch_mcp.api.dto.standalone_valuation_dto import StandaloneValuationDto
from deweloperuch_mcp.api.http.json_endpoint import JsonEndpoint
from deweloperuch_mcp.api.http.transport import HttpClient
from deweloperuch_mcp.api.queries.valuation_query import ValuationQuery
from deweloperuch_mcp.models.valuation import Valuation, ValuationSubject


class ValuationApi:
    """``usecases.ports.ValuationSource`` of the service; ``standalone_valuation`` is its
    resource as the service sends it (DTO)."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def valuation(self, subject: ValuationSubject) -> Valuation:
        return self.standalone_valuation(ValuationQuery(subject)).to_model(subject)

    def standalone_valuation(self, query: ValuationQuery) -> StandaloneValuationDto:
        """``GET /api/standalone-valuation`` [P] at ``query``'s address."""
        target = HttpClient.target(query.path(), query.params())
        return JsonEndpoint(self._http, target).get(StandaloneValuationDto)
