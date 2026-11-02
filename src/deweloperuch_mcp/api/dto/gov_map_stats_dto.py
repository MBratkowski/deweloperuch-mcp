"""``GovMapStatsDto``: ``GET /api/statystyki/gov-map-stats`` [P 2026-11-01] (sample
``api.gov_map_stats``), the latest value of seven official indicators for each of the 66
cities with powiat rights.

``asOf`` names the period of each indicator as text (``08.2026``, ``2025``, ``Q2 2026``),
read into the labels of ``models.government_statistics`` (``2026-08``, ``2025``,
``2026-Q2``); a period in another form is no period (``None``). ``rows`` hold ``slug`` and
``values``; a value is a number or ``null`` (``nbpCena`` in 49 of 66 rows [P 2026-11-01,
P 2026-11-02]), and an absent key counts as ``null`` too. An indicator whose key is
missing from ``asOf`` is a changed service, not 66 cities without it.

What each value is [P 2026-11-02, tests/contract/api/dto/test_gov_map_stats_dto.py, the
capture against the pages of Warszawa and Wrocław, tests/fixtures/rsc/
stats_gov_{warszawa_20261031,wroclaw_20261030}.rsc]: ``bezrobocie`` the unemployment rate
of the month, ``wynagrodzenie`` the gross wage of the year, ``przyrost`` the natural
increase of the year, ``nbpCena`` the NBP transaction price of the secondary market of the
quarter, each the value of the page's series for that period; ``oddane`` and
``rozpoczete`` the sums of the 12 months ending in that month (the page's own chart
„suma 12 miesięcy”). ``powierzchnia`` matches no series of the page (Warszawa 56.78
against 56.7 for 2025 and 56.5 for 2026): the value as the service gives it.
"""

import re

from deweloperuch_mcp.api.dto.dto import Dto, Number
from deweloperuch_mcp.api.dto.government_stats_page_dto import SECTIONS
from deweloperuch_mcp.models.errors import SERVICE_CHANGED, UnexpectedResponseError
from deweloperuch_mcp.models.government_statistics import Dataset
from deweloperuch_mcp.models.indicator_ranking import CityIndicator, Indicator, IndicatorValues
from deweloperuch_mcp.models.location_ranking import PlaceNames

KEYS = {
    Indicator.UNEMPLOYMENT_RATE: "bezrobocie",
    Indicator.AVERAGE_WAGE: "wynagrodzenie",
    Indicator.DWELLINGS_COMPLETED: "oddane",
    Indicator.DWELLINGS_STARTED: "rozpoczete",
    Indicator.AVERAGE_DWELLING_AREA: "powierzchnia",
    Indicator.NATURAL_INCREASE: "przyrost",
    Indicator.NBP_PRICE_PER_M2: "nbpCena",
}
"""The service's key of each indicator, in ``asOf`` and in each row's ``values``."""

DATASETS = {
    Indicator.UNEMPLOYMENT_RATE: Dataset.UNEMPLOYMENT,
    Indicator.AVERAGE_WAGE: Dataset.WAGES,
    Indicator.DWELLINGS_COMPLETED: Dataset.DWELLINGS_MONTHLY,
    Indicator.DWELLINGS_STARTED: Dataset.DWELLINGS_MONTHLY,
    Indicator.AVERAGE_DWELLING_AREA: Dataset.AVERAGE_AREA,
    Indicator.NATURAL_INCREASE: Dataset.DEMOGRAPHY,
    Indicator.NBP_PRICE_PER_M2: Dataset.NBP_PRICES,
}
"""The dataset of the government statistics each indicator belongs to: its section is the
anchor of a city's page (the first of ``SECTIONS``, the one a city's page lists). [P] for
Warszawa and Wrocław, whose pages list the same eight sections (tests/fixtures/rsc/
stats_gov_{warszawa_20261031,wroclaw_20261030}.rsc); [W] for the other 64 cities, pages of
the same route."""

_PERIODS = (
    (re.compile(r"(0[1-9]|1[0-2])\.(\d{4})"), r"\2-\1"),
    (re.compile(r"Q([1-4]) (\d{4})"), r"\2-Q\1"),
    (re.compile(r"(\d{4})"), r"\1"),
)
"""``asOf`` as the service writes it [P 2026-11-01] -> a period label."""


class GovValuesDto(Dto):
    """The values of one city: only the seven keys of ``KEYS`` are read (absent: no value);
    any other key, of any type, is ignored."""

    bezrobocie: Number | None = None
    wynagrodzenie: Number | None = None
    oddane: Number | None = None
    rozpoczete: Number | None = None
    powierzchnia: Number | None = None
    przyrost: Number | None = None
    nbpCena: Number | None = None


class GovPeriodsDto(Dto):
    """``asOf``: the period of each of the seven indicators as text; other keys ignored."""

    bezrobocie: str | None = None
    wynagrodzenie: str | None = None
    oddane: str | None = None
    rozpoczete: str | None = None
    powierzchnia: str | None = None
    przyrost: str | None = None
    nbpCena: str | None = None


class GovCityDto(Dto):
    """One city: its slug and its indicators by the service's keys."""

    slug: str
    values: GovValuesDto

    def to_model(self, key: str, names: PlaceNames) -> CityIndicator:
        slug = self.slug.strip()
        value: int | float | str | None = getattr(self.values, key)
        return CityIndicator(city_slug=slug, name=names.city(slug), value=self._number(value))


class GovMapStatsDto(Dto):
    """The 66 cities (row order as the service sends them) and the periods of the values."""

    asOf: GovPeriodsDto
    rows: list[GovCityDto]

    def to_model(self, indicator: Indicator, names: PlaceNames, *, path: str) -> IndicatorValues:
        key = KEYS[indicator]
        stated: str | None = getattr(self.asOf, key)
        if stated is None:
            raise UnexpectedResponseError(
                f"Serwis nie podaje okresu wskaźnika {indicator.value}. {SERVICE_CHANGED}",
                detail=f"{path}: brak klucza {key!r} w asOf",
            )
        return IndicatorValues(
            indicator=indicator,
            period=self._period(stated),
            cities=tuple(row.to_model(key, names) for row in self.rows if row.slug.strip()),
            section=SECTIONS[DATASETS[indicator]][0],
        )

    @staticmethod
    def _period(stated: str) -> str | None:
        for pattern, label in _PERIODS:
            if pattern.fullmatch(stated.strip()):
                return pattern.sub(label, stated.strip())
        return None
