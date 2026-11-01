"""``TransactionStatisticsApi``: the transaction statistics of a city, the
``TransactionStatisticsSource`` port, from two internal channels of the site (D21): a page
of its UI and a JSON route its own client no longer calls. Either may change without
notice; a removed route or a redirect is a changed service (the transport), never an
unknown city.

- months: the prop ``view`` of ``/statystyki/{city}/transakcje``, read as RSC
  [P 2026-10-31] (``TransactionStatsPageDto``): flats of the secondary market, one row a
  month from 2017-01 to the newest month with transactions (the page's empty months after
  it are dropped). Nothing is sent besides the path: the property type is a path segment
  (houses: ``…/transakcje/domy`` [P z kodu], not read, T75), and the page's
  ``filterMarket`` is applied in the browser only [P 2026-10-31];
- quarters: ``GET /api/avg-price-trend/city/{city}`` [P] (sample ``api.avg_trend_city``),
  without ``type`` or ``metric`` (houses, plots), still served on 2.0 [P 2026-10-30].

A city the service does not know: the page answers a 404 with a flight stream
[P 2026-10-31] and the trend a JSON 404 ``{"error": "Unknown city"}`` [P 2026-10-30]
(docs/discovery/endpoints.md section 9); the transport reads both as ``NotFoundError``.
"""

from collections.abc import Sequence

from deweloperuch_mcp.api.dto.city_trend_dto import CityTrendDto
from deweloperuch_mcp.api.dto.transaction_stats_page_dto import TransactionStatsPageDto
from deweloperuch_mcp.api.http.json_endpoint import JsonEndpoint
from deweloperuch_mcp.api.http.rsc_page import RscPage
from deweloperuch_mcp.api.http.transport import HttpClient
from deweloperuch_mcp.models.errors import SERVICE_CHANGED, UnexpectedResponseError
from deweloperuch_mcp.models.transaction_series import (
    Granularity,
    TransactionCity,
    TransactionPeriod,
    TransactionSeries,
)

CITY_TREND_PATH = "/api/avg-price-trend/city/"


class TransactionStatisticsApi:
    """``usecases.ports.TransactionStatisticsSource`` of the service: one request per city
    and granularity (the transport's cache answers a repeat); ``transaction_stats_page``
    and ``city_price_trend`` are its resources as the service sends them (DTOs)."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def transaction_series(
        self, city: TransactionCity, granularity: Granularity
    ) -> TransactionSeries:
        if granularity is Granularity.MONTH:
            months = self.transaction_stats_page(city.value).to_model()
            return self._series(self.stats_path(city.value), city, granularity, months)
        quarters = self.city_price_trend(city.value).to_model()
        return self._series(CITY_TREND_PATH + "{citySlug}", city, granularity, quarters)

    def transaction_stats_page(self, city_slug: str) -> TransactionStatsPageDto:
        """The prop ``view`` of the statistics page of ``city_slug``: its months. Checked
        while the transport reads the page (``RscPage.prop``), so a page refused here is
        never kept in its cache. [P 2026-10-31] the page answers an unknown city with its own
        404 ``text/x-component``: the route opts in (``unknown_404``)."""
        page = RscPage(self._http, self.stats_path(city_slug), unknown_404=True)
        return page.prop("view", TransactionStatsPageDto)

    def city_price_trend(self, city_slug: str) -> CityTrendDto:
        """Every quarter of the price trend of ``city_slug``."""
        target = CITY_TREND_PATH + HttpClient.segment(city_slug)
        return JsonEndpoint(self._http, target).get(CityTrendDto)

    @staticmethod
    def stats_path(city_slug: str) -> str:
        """``/statystyki/{city}/transakcje``: the transaction statistics page of a city
        (flats), an internal page of the site's UI (D21). [P 2026-10-31] ``warszawa`` and
        ``karpacz``; [W] other cities, the same route."""
        return f"/statystyki/{HttpClient.segment(city_slug)}/transakcje"

    @staticmethod
    def _series(
        path: str,
        city: TransactionCity,
        granularity: Granularity,
        periods: Sequence[TransactionPeriod],
    ) -> TransactionSeries:
        """The periods oldest first. [W] the service lists them in that order already;
        labels sort in time order, so another order costs nothing, but a period twice (or
        a negative count) means the service's data is inconsistent."""
        try:
            return TransactionSeries(
                city, granularity, tuple(sorted(periods, key=lambda item: item.period))
            )
        except ValueError as err:
            raise UnexpectedResponseError(
                f"Statystyki transakcji z serwisu są niespójne. {SERVICE_CHANGED}",
                detail=f"{path}: {err}",
            ) from err
