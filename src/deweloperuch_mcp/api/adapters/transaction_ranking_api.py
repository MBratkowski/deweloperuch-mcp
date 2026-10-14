"""``TransactionRankingApi``: the transactions of every city or powiat, the
``TransactionRankingSource`` port, over ``/api/city-transaction-stats`` and
``/api/map/powiat-stats`` [P] (samples ``api.city_tx_stats``, ``api.powiat_stats``).

Both are sent without a query, as their samples were captured. The heading of
``map/powiat-stats`` names ``type=house|both``, but no sample or observation tests it,
and ``city-transaction-stats`` documents no parameter at all: the ranking has no property
type (docs/discovery/endpoints.md, sections 3 and 4).
"""

from deweloperuch_mcp.api.dto.city_transactions_list_dto import CityTransactionsListDto
from deweloperuch_mcp.api.dto.powiat_transactions_list_dto import PowiatTransactionsListDto
from deweloperuch_mcp.api.http.json_endpoint import JsonEndpoint
from deweloperuch_mcp.api.http.transport import HttpClient
from deweloperuch_mcp.models.location_ranking import LocationTransactions, RankingLevel

CITY_RANKING = "/api/city-transaction-stats"
POWIAT_RANKING = "/api/map/powiat-stats"


class TransactionRankingApi:
    """``usecases.ports.TransactionRankingSource`` of the service: one request per level;
    repeats within the cache's TTL (at most 5 minutes, D2) are answered by the client's
    cache. ``city_transaction_stats`` and ``powiat_stats`` are its resources as the service
    sends them (DTOs)."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def locations(self, level: RankingLevel) -> tuple[LocationTransactions, ...]:
        if level is RankingLevel.POWIAT:
            return self.powiat_stats().to_model()
        return self.city_transaction_stats().to_model()

    def city_transaction_stats(self) -> CityTransactionsListDto:
        """``GET /api/city-transaction-stats`` [P], without a query (none is documented)."""
        return JsonEndpoint(self._http, CITY_RANKING).get(CityTransactionsListDto)

    def powiat_stats(self) -> PowiatTransactionsListDto:
        """``GET /api/map/powiat-stats`` [P], without ``type`` (never tested, see above)."""
        return JsonEndpoint(self._http, POWIAT_RANKING).get(PowiatTransactionsListDto)
