"""``TransactionStatisticsApi``: the transaction statistics of a city, the
``TransactionStatisticsSource`` port, over two JSON endpoints (D1):

- months: ``GET /api/monthly-transaction-stats?propertyType=mieszkania&citySlug={city}``
  [P] (sample ``api.monthly_tx``);
- quarters: ``GET /api/avg-price-trend/city/{city}`` [P] (sample ``api.avg_trend_city``).

Only what the samples were captured with is sent: flats (``propertyType=mieszkania``;
``domy`` is [H]) of a city (``citySlug``; ``powiatRcnId`` and ``street`` were never
called), and the trend without ``type`` or ``metric``.
"""

from collections.abc import Sequence

from deweloperuch_mcp.api.dto.city_trend_dto import CityTrendDto
from deweloperuch_mcp.api.dto.monthly_transaction_stats_dto import MonthlyTransactionStatsDto
from deweloperuch_mcp.api.http.json_endpoint import JsonEndpoint
from deweloperuch_mcp.api.http.transport import HttpClient
from deweloperuch_mcp.models.errors import SERVICE_CHANGED, UnexpectedResponseError
from deweloperuch_mcp.models.transaction_series import (
    Granularity,
    TransactionCity,
    TransactionPeriod,
    TransactionSeries,
)

MONTHLY_PATH = "/api/monthly-transaction-stats"
CITY_TREND_PATH = "/api/avg-price-trend/city/"
FLATS = "mieszkania"
"""``propertyType`` of the sample [P]; houses (``domy``) are [H]."""


class TransactionStatisticsApi:
    """``usecases.ports.TransactionStatisticsSource`` of the service: one request per city
    and granularity (the transport's cache answers a repeat); ``monthly_transaction_stats``
    and ``city_price_trend`` are its resources as the service sends them (DTOs)."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def transaction_series(
        self, city: TransactionCity, granularity: Granularity
    ) -> TransactionSeries:
        if granularity is Granularity.MONTH:
            months = self.monthly_transaction_stats(city.value).to_model()
            return self._series(MONTHLY_PATH, city, granularity, months)
        quarters = self.city_price_trend(city.value).to_model()
        return self._series(CITY_TREND_PATH + "{citySlug}", city, granularity, quarters)

    def monthly_transaction_stats(self, city_slug: str) -> MonthlyTransactionStatsDto:
        """Every month of the transactions of flats in ``city_slug``."""
        target = HttpClient.target(MONTHLY_PATH, [("propertyType", FLATS), ("citySlug", city_slug)])
        return JsonEndpoint(self._http, target).get(MonthlyTransactionStatsDto)

    def city_price_trend(self, city_slug: str) -> CityTrendDto:
        """Every quarter of the price trend of ``city_slug``."""
        target = CITY_TREND_PATH + HttpClient.segment(city_slug)
        return JsonEndpoint(self._http, target).get(CityTrendDto)

    @staticmethod
    def _series(
        path: str,
        city: TransactionCity,
        granularity: Granularity,
        periods: Sequence[TransactionPeriod],
    ) -> TransactionSeries:
        """The periods oldest first. [W] the samples list them in that order already; labels
        sort in time order, so another order costs nothing, but a period twice (or a
        negative count) means the service's data is inconsistent."""
        try:
            return TransactionSeries(
                city, granularity, tuple(sorted(periods, key=lambda item: item.period))
            )
        except ValueError as err:
            raise UnexpectedResponseError(
                f"Statystyki transakcji z serwisu są niespójne. {SERVICE_CHANGED}",
                detail=f"{path}: {err}",
            ) from err
