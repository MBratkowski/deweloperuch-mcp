"""The views of the locations: what ``search_locations`` shows, for the CLI (``--json``)
and for the MCP presenter. Each builds itself from a use case's result (``from_result``)
or a model (``from_model``)."""

from typing import Self

from deweloperuch_mcp.consumers.shared.view import View
from deweloperuch_mcp.models.location import Location
from deweloperuch_mcp.usecases.search_locations import SearchLocationsResult


class LocationView(View):
    """A city, district or street to search in; ``city_slug`` goes to ``search_offers``."""

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
    def from_model(cls, location: Location) -> Self:
        return cls(
            kind=location.kind,
            name=location.name,
            city=location.city,
            city_slug=location.city_slug,
            district=location.district,
            street=location.street,
            lat=location.lat,
            lng=location.lng,
            offer_count=location.offer_count,
        )


class LocationSearchView(View):
    """The locations matching a query, cities first (D4: the cut is explicit)."""

    total: int | None
    """All matches; ``None`` when ``truncated`` (the service does not say how many)."""
    returned: int
    truncated: bool
    """More matches exist than shown: make the query more specific."""
    hint: str | None = None
    items: list[LocationView]

    @classmethod
    def from_result(cls, result: SearchLocationsResult) -> Self:
        found = result.found
        return cls(
            total=found.total,
            returned=found.returned,
            truncated=found.truncated,
            hint=found.hint,
            items=[LocationView.from_model(item) for item in found.items],
        )
