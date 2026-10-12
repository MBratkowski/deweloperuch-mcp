"""Places to search in (D3, D13): cities, districts and streets, and a search for them.

A location carries the ``city_slug`` that an offers search takes. A search asks two
sources (``ports.LocationDirectory``: cities, then districts and streets) and says when
more may match than it shows (D4): then there is no total and the hint asks for a more
specific name.
"""

from dataclasses import dataclass
from typing import Self

from deweloperuch_mcp.domain.values import LocationQuery

CITY, DISTRICT, STREET = "city", "district", "street"
"""Kinds of a location the service names [P]; other kinds pass through unchanged."""


@dataclass(frozen=True, kw_only=True)
class Location:
    """A city, district or street to search in; ``city_slug`` goes to an offers search."""

    kind: str
    """``city``, ``district`` or ``street``."""
    name: str
    city: str
    city_slug: str
    district: str | None = None
    street: str | None = None
    lat: float | None = None
    lng: float | None = None
    offer_count: int | None = None
    """Developer offers in the location (for districts and streets [W])."""

    @classmethod
    def city_of(cls, *, name: str, city_slug: str, offer_count: int | None) -> Self:
        return cls(kind=CITY, name=name, city=name, city_slug=city_slug, offer_count=offer_count)

    @classmethod
    def place(
        cls,
        *,
        kind: str,
        city: str,
        city_slug: str,
        district: str | None,
        street: str | None,
        lat: float | None,
        lng: float | None,
        offer_count: int | None,
    ) -> Self:
        """A district or street, named after what it is; another kind ([H]) after the most
        specific name it has; without any, after its city."""
        if kind == STREET:
            name = street
        elif kind == DISTRICT:
            name = district
        else:
            name = street or district
        return cls(
            kind=kind,
            name=name or city,
            city=city,
            city_slug=city_slug,
            district=district,
            street=street,
            lat=lat,
            lng=lng,
            offer_count=offer_count,
        )


@dataclass(frozen=True)
class LocationMatches:
    """What one source matched, and whether it may have more than it gave."""

    items: tuple[Location, ...]
    more: bool = False


@dataclass(frozen=True)
class LocationSearchResult:
    """The locations matching a query, cities first (D4: the cut is explicit)."""

    query: LocationQuery
    items: tuple[Location, ...]
    truncated: bool
    """More matches may exist than shown: make the query more specific."""

    @classmethod
    def of(cls, query: LocationQuery, *matches: LocationMatches) -> Self:
        return cls(
            query=query,
            items=tuple(item for found in matches for item in found.items),
            truncated=any(found.more for found in matches),
        )

    @property
    def total(self) -> int | None:
        """All matches; ``None`` when ``truncated`` (the service does not say how many)."""
        return None if self.truncated else len(self.items)

    @property
    def returned(self) -> int:
        return len(self.items)

    @property
    def hint(self) -> str | None:
        if self.truncated:
            return "Pasujących lokalizacji może być więcej: doprecyzuj nazwę (np. dodaj miasto)."
        if not self.items:
            return (
                f"Nic nie pasuje do {self.query.text!r}. Sprawdź pisownię (z polskimi znakami) "
                "albo podaj początek nazwy miasta, dzielnicy lub ulicy."
            )
        return None
