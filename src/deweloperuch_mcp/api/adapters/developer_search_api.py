"""``DeveloperSearchApi``: developers by a part of their name, the ``DeveloperSearch`` port.

- ``GET /api/developers?q=&limit=`` [P] (docs/discovery/endpoints.md, sample
  ``api.developers_q``: ``q=atal&limit=5``). Sent: ``q`` and ``limit`` [P]. Not sent:
  ``page`` (not documented for this endpoint) and the search context the UI adds
  (``city``, ``minPrice``...), whose effect is untested.
"""

from deweloperuch_mcp.api.dto.developers_dto import DevelopersDto
from deweloperuch_mcp.api.http.json_endpoint import JsonEndpoint
from deweloperuch_mcp.api.http.transport import HttpClient
from deweloperuch_mcp.models.developer_match import DeveloperMatches, DeveloperName, MatchCount


class DeveloperSearchApi:
    """``usecases.ports.DeveloperSearch`` of the service; ``named_developers`` is its
    resource as the service sends it (DTO)."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def developers(self, name: DeveloperName, count: MatchCount) -> DeveloperMatches:
        # [W] docs/discovery/endpoints.md, /api/developers: a ``limit`` other than the UI's
        # 5 is honoured like that of /api/location-search (up to at least 20 [P]); the
        # domain cuts the matches to the count anyway.
        return self.named_developers(name.text, count.value).to_model()

    def named_developers(self, query: str, limit: int) -> DevelopersDto:
        """``GET /api/developers?q=&limit=`` [P]: developers whose name matches ``query``."""
        target = HttpClient.target("/api/developers", [("q", query), ("limit", limit)])
        return JsonEndpoint(self._http, target).get(DevelopersDto)
