"""``DeveloperPageDto``: prop ``data`` of ``/ceny-ofertowe/{city}/deweloperzy/{developerSlug}``
(RSC) [P] (sample ``page.developer``, tests/fixtures/rsc/developer_*), a developer's profile.

The meaning of the figures read here is [P 2026-10-13]: checked against the page's own
list of offers (prop ``sale``) and investments in
tests/contract/api/dto/test_developer_page_dto.py. Not read:
``priceIncrease*``/``priceDecrease*`` (the counts are 0 while the sums are not: unclear),
``allCities``, ``allCitiesWithSlugs``, ``allInvestmentNames``, the ``sale`` list and the
daily change axis (prop ``data`` as a list).

The averages of the page (``filteredStats``, its investments and its cities) are 0 where
the service has no value: a developer without active offers in that city gets
``averagePrice``, ``averageSize`` and ``avgAmountPerM2`` 0 [P 2026-10-20] (live: ``atal``
in ``bialystok``). 0 is no value, not a price (``Dto._positive``).

Since the 2.0 build (2026-10-29) the page has no ``data`` prop [P 2026-10-30, live RSC
payload of the package client, ``archicom`` in ``polska``]: the developer is the scalar
props ``developerSlug``, ``developerName`` and ``developerId``, its investments the prop
``investments`` (rows with the same fields), and its cities the rows of the chart spec
``ceny-w-miastach`` (``key``, ``label``, ``value`` = average PLN/m², ``extra`` = active
offers, ``tip`` with the investments). ``filteredStats`` has no counterpart:
``from_props`` computes it from the investments (the averages weighted by their active
offers, which is how the page's own ``ceny-w-miastach`` averages come out: Wrocław
15 490 PLN/m² from its four investments). The developer's website and description are
not on the 2.0 page (``developer`` is ``null``).
"""

from collections.abc import Mapping, Sequence
from typing import Any, Self

from pydantic import Field

from deweloperuch_mcp.api.dto.developer_dto import DeveloperDto
from deweloperuch_mcp.api.dto.dto import Dto, Number
from deweloperuch_mcp.models.developer_profile import (
    DeveloperCity,
    DeveloperInvestment,
    DeveloperProfile,
    DeveloperSummary,
)
from deweloperuch_mcp.models.errors import SERVICE_CHANGED, UnexpectedResponseError
from deweloperuch_mcp.models.offer import DeveloperRef
from deweloperuch_mcp.models.values import CitySlug


class DeveloperInvestmentDto(Dto):
    """An investment of the profile; ``avg_*`` of its active offers."""

    invest_id: int | None = None
    name: str
    city: str | None = None
    city_slug: str | None = None
    slug: str
    status: str
    active_offers: int | None = None
    total_offers: int | None = None
    avg_amount: Number | None = None
    avg_size: Number | None = None
    avg_price_sqm: Number | None = None

    def to_model(self, developer: DeveloperRef) -> DeveloperInvestment:
        """The investment of ``developer`` (the profile's owner)."""
        return DeveloperInvestment(
            investment_slug=self.slug,
            name=self.name,
            city=self._text(self.city),
            city_slug=self._text(self.city_slug),
            status=self.status,
            active_offers=self.active_offers,
            total_offers=self.total_offers,
            avg_price=self._positive(self.avg_amount),
            avg_area_m2=self._positive(self.avg_size),
            avg_price_per_m2=self._positive(self.avg_price_sqm),
            developer=developer,
        )


class DeveloperFilteredStatsDto(Dto):
    """The developer's active offers in the page's city (or the whole country)."""

    totalProjects: int | None = None
    totalSales: int | None = None
    totalCities: int | None = None
    averagePrice: Number | None = None
    averageSize: Number | None = None
    avgAmountPerM2: Number | None = None

    def to_model(self) -> DeveloperSummary:
        return DeveloperSummary(
            investments=self.totalProjects,
            active_offers=self.totalSales,
            cities=self.totalCities,
            avg_price=self._positive(self.averagePrice),
            avg_area_m2=self._positive(self.averageSize),
            avg_price_per_m2=self._positive(self.avgAmountPerM2),
        )


class DeveloperCityStatsDto(Dto):
    """A city of the developer (every city, whatever the page's city)."""

    city: str
    citySlug: str
    investmentCount: int | None = None
    activeOffersCount: int | None = None
    avgPricePerM2: Number | None = None
    avgPrice: Number | None = None

    def to_model(self) -> DeveloperCity:
        return DeveloperCity(
            city=self.city,
            city_slug=self.citySlug,
            investments=self.investmentCount,
            active_offers=self.activeOffersCount,
            avg_price=self._positive(self.avgPrice),
            avg_price_per_m2=self._positive(self.avgPricePerM2),
        )


DEVELOPER_PROPS = ("data", "developerName", "developerId", "investments", "spec")
"""The props ``from_props`` reads (``developerSlug`` too, but it only repeats the URL)."""
CITIES_SPEC = "ceny-w-miastach"
"""The id of the 2.0 chart spec with the developer's cities."""


def _first(props: Mapping[str, list[Any]], name: str, kind: type | tuple[type, ...]) -> Any:
    return next((value for value in props.get(name, ()) if isinstance(value, kind)), None)


def _spec_rows(specs: Sequence[Any], spec_id: str) -> list[Mapping[str, Any]]:
    """The rows of the first view of the chart spec ``spec_id``; none without one."""
    spec = next((s for s in specs if isinstance(s, dict) and s.get("id") == spec_id), {})
    views = spec.get("views")
    view: Any = next(iter(views.values()), {}) if isinstance(views, dict) and views else {}
    rows = view.get("rows") if isinstance(view, dict) else None
    return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []


def _count(value: object) -> int | None:
    """``345``, ``"345"`` -> 345; anything else ``None``."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isascii() and value.strip().isdigit():
        return int(value.strip())
    return None


class DeveloperPageDto(Dto):
    """Prop ``data`` of ``/ceny-ofertowe/{city}/deweloperzy/{developerSlug}`` [P]."""

    developer: DeveloperDto
    investments: list[DeveloperInvestmentDto]
    filteredStats: DeveloperFilteredStatsDto
    citiesStats: list[DeveloperCityStatsDto] = Field(default_factory=list)

    @classmethod
    def from_props(cls, props: Mapping[str, list[Any]], *, path: str, slug: str) -> Self:
        """The profile from ``DEVELOPER_PROPS`` (``RscPage.props``): the object ``data`` as
        it is, or the 2.0 props (see the module docstring); ``slug`` is the requested one."""
        old = _first(props, "data", dict)
        if old is not None:
            return Dto.validated(cls, old, f"{path} (prop data)")
        name = _first(props, "developerName", str)
        investments = _first(props, "investments", list)
        if name is None or investments is None:
            raise UnexpectedResponseError(
                f"Na stronie serwisu brakuje oczekiwanych danych. {SERVICE_CHANGED}",
                detail=f"{path}: brak propsów developerName i investments (2.0)",
            )
        rows = [row for row in investments if isinstance(row, dict)]
        developer_id = _first(props, "developerId", int)
        data = {
            "developer": {"developer_id": developer_id, "name": name, "slug": slug},
            "investments": rows,
            "filteredStats": {
                "totalProjects": len(rows),
                "totalSales": sum(_count(row.get("active_offers")) or 0 for row in rows),
                "totalCities": len({row.get("city_slug") for row in rows}),
                "averagePrice": cls._weighted(rows, "avg_amount"),
                "averageSize": cls._weighted(rows, "avg_size"),
                "avgAmountPerM2": cls._weighted(rows, "avg_price_sqm"),
            },
            "citiesStats": cls._cities(props.get("spec", []), rows),
        }
        return Dto.validated(cls, data, f"{path} (propsy 2.0)")

    @classmethod
    def _weighted(cls, rows: Sequence[Mapping[str, Any]], field: str) -> float | None:
        """The mean of ``field`` over ``rows`` weighted by their active offers (rows without
        offers or without a value left out); ``None`` when no row counts."""
        total = weight = 0.0
        for row in rows:
            offers, value = _count(row.get("active_offers")), cls._number(row.get(field))
            if offers and value is not None and value > 0:
                total += value * offers
                weight += offers
        return round(total / weight, 2) if weight else None

    @classmethod
    def _cities(
        cls, specs: Sequence[Any], rows: Sequence[Mapping[str, Any]]
    ) -> list[dict[str, Any]]:
        """The rows of the ``CITIES_SPEC`` chart as ``DeveloperCityStatsDto`` data; the
        average price of a city comes from its investments on the page, when it has any."""
        return [
            cls._city(item, [row for row in rows if row.get("city_slug") == item.get("key")])
            for item in _spec_rows(specs, CITIES_SPEC)
        ]

    @classmethod
    def _city(cls, item: Mapping[str, Any], own: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        """One row of ``CITIES_SPEC``: ``tip`` holds the number of investments."""
        tip = item.get("tip")
        tips = tip.get("rows", ()) if isinstance(tip, dict) else ()
        counts = {t.get("key"): t.get("value") for t in tips if isinstance(t, dict)}
        return {
            "city": item.get("label"),
            "citySlug": item.get("key"),
            "investmentCount": _count(counts.get("inwestycje")),
            "activeOffersCount": _count(item.get("extra")),
            "avgPricePerM2": item.get("value"),
            "avgPrice": cls._weighted(own, "avg_amount"),
        }

    def to_model(self, city: CitySlug) -> DeveloperProfile:
        """The profile in ``city`` (the page's): its investments in the service's order,
        every city."""
        owner = self.developer.to_model()
        return DeveloperProfile(
            developer=owner,
            city=city,
            summary=self.filteredStats.to_model(),
            investments=tuple(item.to_model(owner) for item in self.investments),
            cities=tuple(item.to_model() for item in self.citiesStats),
        )
