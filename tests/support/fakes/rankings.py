"""``TransactionRankingSource``, ``CityIndicatorSource`` and ``RankingLinks`` in memory, and
the places they rank."""

import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from deweloperuch_mcp.models.indicator_ranking import CityIndicator, Indicator, IndicatorValues
from deweloperuch_mcp.models.location_ranking import (
    LocationTransactions,
    PowiatTransactions,
    RankingMarket,
    TransactionPeriod,
)
from deweloperuch_mcp.models.values import LocationSlug
from deweloperuch_mcp.usecases import ports
from support.paths import API_FIXTURES, PACKAGE_SOURCE


def city(
    name: str, count: int, price_per_m2: float | None = 10_000.0, slug: str | None = None
) -> LocationTransactions:
    return LocationTransactions(
        name=name,
        city_slug=slug or name.lower(),
        transaction_count=count,
        price_per_m2=price_per_m2,
        area_m2=50.0,
        price=500_000.0,
    )


# Figures of the sample api.city_tx_stats [P 2026-10-09] and made-up small places.
WARSZAWA = city("Warszawa", 3606, 16413.0)


KRAKOW = city("Kraków", 1492, 14606.0, "krakow")


WROCLAW = city("Wrocław", 1443, 12437.0, "wroclaw")


VILLAGE = city("Wieś", 1, 30_000.0)


NO_PRICE = city("Bez ceny", 2, None)


CITIES = (WROCLAW, VILLAGE, WARSZAWA, NO_PRICE, KRAKOW)


def powiat(
    name: str, powiat_id: int, count: int, price_per_m2: float, area_m2: float, price: float
) -> LocationTransactions:
    return LocationTransactions(
        name=name,
        powiat_id=powiat_id,
        transaction_count=count,
        price_per_m2=price_per_m2,
        area_m2=area_m2,
        price=price,
    )


# Figures of tests/fixtures/api/powiat_map_stats_20261102.json [P 2026-11-02]: powiat
# Warszawa (302), Kraków (14) and Sopot (208), whose primary market is null.
SOPOT_SECONDARY = powiat("powiat Sopot", 208, 310, 18468.0, 54.6, 1071000.0)


POWIATS = PowiatTransactions(
    period=TransactionPeriod(start="2025-11-01", end="2026-10"),
    powiats=3,
    markets={
        RankingMarket.SECONDARY: (
            powiat("powiat Warszawa", 302, 14563, 16395.0, 48.6, 779000.0),
            powiat("powiat Kraków", 14, 6120, 14812.0, 47.5, 685000.0),
            SOPOT_SECONDARY,
        ),
        RankingMarket.PRIMARY: (
            powiat("powiat Warszawa", 302, 17531, 15468.0, 46.8, 764088.0),
            powiat("powiat Kraków", 14, 7444, 14969.0, 51.0, 755045.0),
        ),
        RankingMarket.ALL: (
            powiat("powiat Warszawa", 302, 32095, 15903.0, 47.9, 770000.0),
            powiat("powiat Kraków", 14, 13383, 14940.0, 48.9, 725000.0),
            powiat("powiat Sopot", 208, 409, 19825.0, 54.1, 1100000.0),
        ),
    },
)


GOV_MAP_STATS_2026_11_02 = API_FIXTURES / "gov_map_stats_20261102.json"


PLACE_NAMES = PACKAGE_SOURCE / "api" / "data" / "place_names.json"


def indicator_values(
    indicator: Indicator, key: str, slugs: tuple[str, ...] | None = None
) -> IndicatorValues:
    """The values of ``key`` in tests/fixtures/api/gov_map_stats_20261102.json, as the
    domain has them (the cities named as the packaged table names them); ``slugs``: only
    these cities."""
    body = json.loads(GOV_MAP_STATS_2026_11_02.read_bytes())
    names = json.loads(PLACE_NAMES.read_bytes())["cities"]
    period = {"Q2 2026": "2026-Q2", "08.2026": "2026-08", "2025": "2025"}[body["asOf"][key]]
    return IndicatorValues(
        indicator=indicator,
        period=period,
        cities=tuple(
            CityIndicator(city_slug=row["slug"], name=names[row["slug"]], value=row["values"][key])
            for row in body["rows"]
            if slugs is None or row["slug"] in slugs
        ),
        section=None,
    )


NBP_PRICES = indicator_values(Indicator.NBP_PRICE_PER_M2, "nbpCena")
"""Every city of the capture: 17 with a price, 49 without."""


UNEMPLOYMENT = indicator_values(
    Indicator.UNEMPLOYMENT_RATE, "bezrobocie", ("warszawa", "poznan", "bialystok", "radom")
)
"""Four cities of the capture, two of them with the same rate (1.6 %)."""


@dataclass
class FakeRankingSource:
    """``TransactionRankingSource`` that answers from ``cities_are`` and ``powiats_are``
    or raises ``error``."""

    cities_are: tuple[LocationTransactions, ...] = CITIES
    powiats_are: PowiatTransactions = POWIATS
    error: Exception | None = None
    asked: list[str] = field(default_factory=list)

    def cities(self) -> tuple[LocationTransactions, ...]:
        self.asked.append("cities")
        if self.error is not None:
            raise self.error
        return self.cities_are

    def powiats(self) -> PowiatTransactions:
        self.asked.append("powiats")
        if self.error is not None:
            raise self.error
        return self.powiats_are


@dataclass
class FakeIndicatorSource:
    """``CityIndicatorSource`` that answers from ``values`` (by indicator) or raises
    ``error``."""

    values: dict[Indicator, IndicatorValues] = field(
        default_factory=lambda: {
            Indicator.NBP_PRICE_PER_M2: NBP_PRICES,
            Indicator.UNEMPLOYMENT_RATE: UNEMPLOYMENT,
        }
    )
    error: Exception | None = None
    asked: list[Indicator] = field(default_factory=list)

    def indicator(self, indicator: Indicator) -> IndicatorValues:
        self.asked.append(indicator)
        if self.error is not None:
            raise self.error
        return self.values[indicator]


class FakeRankingLinks:
    def city_ranking(self) -> str | None:
        return "<ranking miast>"

    def government_statistics(self, location: LocationSlug, section: str | None) -> str | None:
        return f"<dane rządowe {location.value}#{section}>"


if TYPE_CHECKING:  # mypy checks that each fake is the port it stands in for
    _transaction_ranking_source: ports.TransactionRankingSource = FakeRankingSource()
    _city_indicator_source: ports.CityIndicatorSource = FakeIndicatorSource()
    _ranking_links: ports.RankingLinks = FakeRankingLinks()
