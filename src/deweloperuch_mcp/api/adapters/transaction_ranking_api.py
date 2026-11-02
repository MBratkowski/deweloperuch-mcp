"""``TransactionRankingApi``: the transactions of every city or powiat, the
``TransactionRankingSource`` port, over ``/api/city-transaction-stats`` [P] (sample
``api.city_tx_stats``) and ``/api/statystyki/powiat-map-stats`` [P 2026-11-01] (sample
``api.powiat_map_stats``).

Both are sent without a query: ``city-transaction-stats`` documents no parameter, and any
query string on ``powiat-map-stats`` is refused (docs/discovery/endpoints.md, sections 3
and 4). The powiats of 1.0 came from ``/api/map/powiat-stats``, an HTML 404 since
2026-10-29 (D21).
"""

from deweloperuch_mcp.api.dto.city_transactions_list_dto import CityTransactionsListDto
from deweloperuch_mcp.api.dto.place_names_dto import PlaceNamesDto
from deweloperuch_mcp.api.dto.powiat_map_stats_dto import PowiatMapStatsDto
from deweloperuch_mcp.api.http.json_endpoint import JsonEndpoint
from deweloperuch_mcp.api.http.transport import HttpClient
from deweloperuch_mcp.models.location_ranking import LocationTransactions, PowiatTransactions

CITY_RANKING = "/api/city-transaction-stats"
POWIAT_RANKING = "/api/statystyki/powiat-map-stats"


class TransactionRankingApi:
    """``usecases.ports.TransactionRankingSource`` of the service: one request per level;
    repeats within the cache's TTL are answered by the client's cache (D2, D19).
    ``city_transaction_stats`` and ``powiat_map_stats`` are its resources as the service
    sends them (DTOs); the powiats are named from the packaged table (``PlaceNamesDto``)."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def cities(self) -> tuple[LocationTransactions, ...]:
        return self.city_transaction_stats().to_model()

    def powiats(self) -> PowiatTransactions:
        return self.powiat_map_stats().to_model(PlaceNamesDto.packaged().to_model())

    def city_transaction_stats(self) -> CityTransactionsListDto:
        """``GET /api/city-transaction-stats`` [P], without a query (none is documented)."""
        return JsonEndpoint(self._http, CITY_RANKING).get(CityTransactionsListDto)

    def powiat_map_stats(self) -> PowiatMapStatsDto:
        """``GET /api/statystyki/powiat-map-stats`` [P 2026-11-01], without a query."""
        return JsonEndpoint(self._http, POWIAT_RANKING).get(PowiatMapStatsDto)
