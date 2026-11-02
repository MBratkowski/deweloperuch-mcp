"""Use case ``RankLocations``: cities or powiats ranked by their RCN transactions, or the
cities with powiat rights ranked by an official indicator, with what to do about the
places left out (by the price orders' default threshold, by a market or an indicator the
service has no figures for) and the service's pages of the ranking."""

from dataclasses import dataclass
from typing import Self

from deweloperuch_mcp.models.errors import InvalidInputError, InvalidValueError
from deweloperuch_mcp.models.indicator_ranking import (
    Indicator,
    IndicatorCriteria,
    IndicatorRanking,
)
from deweloperuch_mcp.models.location_ranking import (
    DEFAULT_RANKING_LIMIT,
    RANKING_LIMIT_MAX,
    LocationRanking,
    MinTransactions,
    RankingCriteria,
    RankingLevel,
    RankingLimit,
    RankingMarket,
    RankingOrder,
    TransactionPeriod,
)
from deweloperuch_mcp.models.values import LocationSlug
from deweloperuch_mcp.usecases.ports import (
    CityIndicatorSource,
    RankingLinks,
    TransactionRankingSource,
)
from deweloperuch_mcp.usecases.support.arguments import ParameterCheck
from deweloperuch_mcp.usecases.support.failures import ReportedAs

INDICATOR_NEEDS_CITIES = (
    "indicator działa tylko z level=city: wskaźniki GUS/NBP są tylko dla 66 miast na prawach "
    "powiatu, a dla powiatów są tylko transakcje (market). Pomiń level, aby dostać ranking "
    "miast według wskaźnika, albo pomiń indicator, aby dostać ranking powiatów według "
    "transakcji."
)
INDICATOR_WITHOUT_MIN_TRANSACTIONS = (
    "min_transactions nie działa z indicator: ranking wskaźnika nie liczy transakcji; pomiń "
    "min_transactions."
)
INDICATOR_WITHOUT_MARKET = (
    "market nie działa z indicator: rynek dotyczy transakcji powiatów; pomiń market."
)
INDICATOR_SORTS = (
    "Z indicator sort przyjmuje value_desc (najwyższa wartość, domyślnie) albo value_asc "
    "(najniższa); pomiń sort albo podaj jedną z nich."
)
VALUE_SORTS_NEED_INDICATOR = (
    "sort value_desc i value_asc działa tylko z indicator; podaj indicator albo sort "
    "transactions_desc, price_per_m2_desc lub price_per_m2_asc."
)
MARKET_NEEDS_POWIATS = (
    "market działa tylko z level=powiat: ranking miejscowości nie dzieli transakcji na rynki; "
    "pomiń market albo podaj level=powiat."
)

_MARKETS = {
    RankingMarket.SECONDARY: "rynku wtórnego",
    RankingMarket.PRIMARY: "rynku pierwotnego",
    RankingMarket.ALL: "obu rynków razem",
}
"""The data of each market, in the genitive: „danych rynku wtórnego”."""


def _places(level: RankingLevel) -> str:
    """The places of ``level`` in the genitive plural, as in "Ranking powiatów"."""
    return "powiatów" if level is RankingLevel.POWIAT else "miejscowości"


@dataclass(frozen=True, kw_only=True)
class RankLocationsRequest:
    """What to rank, in which order, how many places and from how many transactions (or by
    which indicator), checked (``parse``) before anything is sent."""

    criteria: RankingCriteria | IndicatorCriteria

    @classmethod
    def parse(  # noqa: PLR0913 - one keyword per parameter of the tool and the command
        cls,
        *,
        level: object = RankingLevel.CITY.value,
        sort: object = None,
        limit: object = DEFAULT_RANKING_LIMIT,
        min_transactions: object = None,
        market: object = None,
        indicator: object = None,
    ) -> Self:
        """Checked in this order: level, sort, limit, min_transactions, market, indicator;
        then what they need of each other. A refusal names the parameter
        (``InvalidInputError``). ``sort`` not given (``None``) is ``transactions_desc``, with
        an indicator ``value_desc``; ``min_transactions`` not given leaves the threshold to
        the order (``RankingCriteria.threshold``); ``market`` not given is the default of a
        powiat ranking (``RankingCriteria.powiat_market``)."""
        with ParameterCheck():
            where = RankingLevel.parse(level)
            order = None if sort is None else RankingOrder.parse(sort)
            count = RankingLimit.parse(limit)
            least = MinTransactions.parse(min_transactions)
            on = None if market is None else RankingMarket.parse(market)
            by = None if indicator is None else Indicator.parse(indicator)
        if by is not None:
            cls._check_indicator(where, order, least, on)
            return cls(criteria=IndicatorCriteria(by, order or RankingOrder.VALUE_DESC, count))
        if order is not None and order.by_value:
            raise InvalidInputError(VALUE_SORTS_NEED_INDICATOR)
        if on is not None and where is not RankingLevel.POWIAT:
            raise InvalidInputError(MARKET_NEEDS_POWIATS)
        return cls(
            criteria=RankingCriteria(
                level=where,
                order=order or RankingOrder.TRANSACTIONS_DESC,
                limit=count,
                min_transactions=least,
                market=on,
            )
        )

    @staticmethod
    def _check_indicator(
        level: RankingLevel,
        order: RankingOrder | None,
        least: MinTransactions | None,
        market: RankingMarket | None,
    ) -> None:
        if level is not RankingLevel.CITY:
            raise InvalidInputError(INDICATOR_NEEDS_CITIES)
        if least is not None:
            raise InvalidInputError(INDICATOR_WITHOUT_MIN_TRANSACTIONS)
        if market is not None:
            raise InvalidInputError(INDICATOR_WITHOUT_MARKET)
        if order is not None and not order.by_value:
            raise InvalidInputError(INDICATOR_SORTS)


@dataclass(frozen=True, kw_only=True)
class RankLocationsResult:
    """The ranking with the service's pages: of the ranking of cities (D12; powiats have
    none) or of each ranked city's government statistics (``stats_urls``, aligned with
    the items of an indicator ranking). ``period``: the months of a powiat ranking;
    ``without_data``: the powiats without figures for the market, or the cities without
    the indicator, left out of the ranking."""

    ranking: LocationRanking | IndicatorRanking
    ranking_url: str | None = None
    period: TransactionPeriod | None = None
    without_data: int = 0
    stats_urls: tuple[str | None, ...] = ()

    @property
    def hint(self) -> str | None:
        """What was left out (by the price orders' default threshold, only when it left
        places out; by a missing market or indicator), and what to do when no place is
        left or the ranking is cut (D4)."""
        if isinstance(self.ranking, IndicatorRanking):
            said = [self._without_indicator(self.ranking), self._indicator_cut(self.ranking)]
        else:
            said = [
                self._left_out_by_default(self.ranking),
                self._without_market(self.ranking),
                self._cut(self.ranking),
            ]
        return " ".join(part for part in said if part) or None

    @staticmethod
    def _left_out_by_default(ranking: LocationRanking) -> str | None:
        criteria = ranking.criteria
        if not (criteria.threshold_by_default and ranking.left_out):
            return None
        return (
            "Przy sortowaniu po cenie pominięto miejsca z mniej niż "
            f"{criteria.threshold.value} transakcjami (domyślny próg); wszystkie miejsca "
            "pokaże min_transactions=0."
        )

    def _without_market(self, ranking: LocationRanking) -> str | None:
        if not self.without_data:
            return None
        market = ranking.criteria.powiat_market
        return (
            f"Pominięto powiaty, dla których serwis nie podaje danych {_MARKETS[market]} "
            f"(market={market.value}): {self.without_data}."
        )

    @staticmethod
    def _cut(ranking: LocationRanking) -> str | None:
        criteria = ranking.criteria
        least = criteria.threshold.value
        if not ranking.items and least:
            return (
                f"Żadne miejsce nie ma co najmniej {least} transakcji: zmniejsz min_transactions."
            )
        if not ranking.truncated:
            return None
        shown = f"Pokazano pierwsze {ranking.returned} z {ranking.total} {_places(criteria.level)}"
        if criteria.limit.value >= RANKING_LIMIT_MAX:
            return (
                f"{shown}; to najwięcej w jednym wywołaniu. Pomiń małe miejsca przez "
                "min_transactions albo zmień sort."
            )
        return f"{shown}; kolejne pokaże większy limit (najwyżej {RANKING_LIMIT_MAX})."

    def _without_indicator(self, ranking: IndicatorRanking) -> str | None:
        if not self.without_data:
            return None
        every = ranking.total + self.without_data
        if not ranking.total:
            return f"Serwis nie podaje tego wskaźnika dla żadnego z {every} miast."
        return (
            "Pominięto miasta, dla których serwis nie podaje tego wskaźnika: "
            f"{self.without_data} z {every}."
        )

    @staticmethod
    def _indicator_cut(ranking: IndicatorRanking) -> str | None:
        if not ranking.truncated:
            return None
        return (
            f"Pokazano pierwsze {ranking.returned} z {ranking.total} miast; kolejne pokaże "
            f"większy limit (najwyżej {RANKING_LIMIT_MAX})."
        )


class RankLocations:
    """One question to a source per ranking; the domain filters, orders and cuts it."""

    def __init__(
        self,
        source: TransactionRankingSource,
        indicators: CityIndicatorSource,
        links: RankingLinks,
    ) -> None:
        self._source = source
        self._indicators = indicators
        self._links = links

    def execute(self, request: RankLocationsRequest) -> RankLocationsResult:
        criteria = request.criteria
        if isinstance(criteria, IndicatorCriteria):
            return self._by_indicator(criteria)
        if criteria.level is RankingLevel.POWIAT:
            return self._powiats(criteria)
        with ReportedAs("Ranking miejscowości"):
            places = self._source.cities()
        ranking = LocationRanking.of(criteria, places)
        return RankLocationsResult(ranking=ranking, ranking_url=self._links.city_ranking())

    def _powiats(self, criteria: RankingCriteria) -> RankLocationsResult:
        with ReportedAs("Ranking powiatów"):
            powiats = self._source.powiats()
        market = criteria.powiat_market
        return RankLocationsResult(
            ranking=LocationRanking.of(criteria, powiats.on(market)),
            period=powiats.period,
            without_data=powiats.without(market),
        )

    def _by_indicator(self, criteria: IndicatorCriteria) -> RankLocationsResult:
        with ReportedAs("Ranking miast według wskaźnika"):
            values = self._indicators.indicator(criteria.indicator)
        ranking = IndicatorRanking.of(criteria, values)
        return RankLocationsResult(
            ranking=ranking,
            without_data=ranking.left_out,
            stats_urls=tuple(
                self._stats_url(item.city_slug, values.section) for item in ranking.items
            ),
        )

    def _stats_url(self, city_slug: str, section: str | None) -> str | None:
        """The city's page of government statistics; none for a slug that is no location."""
        try:
            location = LocationSlug.parse(city_slug)
        except InvalidValueError:
            return None
        return self._links.government_statistics(location, section)
