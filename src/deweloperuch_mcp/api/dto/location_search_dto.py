"""``LocationSearchDto``: ``GET /api/location-search?q=&limit=`` [P] (sample
``api.location_search``), the districts and streets matching a query."""

from deweloperuch_mcp.api.dto.dto import Dto, Number
from deweloperuch_mcp.models.location import Location, LocationMatches


class LocationSuggestionDto(Dto):
    kind: str
    city: str
    citySlug: str
    district: str | None = None
    street: str | None = None
    count: int | None = None
    lat: Number | None = None
    lng: Number | None = None

    def to_model(self) -> Location:
        return Location.place(
            kind=self.kind,
            city=self.city,
            city_slug=self.citySlug,
            district=self._text(self.district),
            street=self._text(self.street),
            lat=self._number(self.lat),
            lng=self._number(self.lng),
            # [W] docs/discovery/endpoints.md, location-search: `count` is the number of offers
            # (or transactions with variant=transactions, never sent) in the area.
            offer_count=self.count,
        )


class LocationSearchDto(Dto):
    suggestions: list[LocationSuggestionDto]

    def to_model(self, limit: int) -> LocationMatches:
        """The suggestions of a request for at most ``limit`` of them."""
        # [W] /api/location-search has no such flag: a full page of suggestions may hide
        # more.
        return LocationMatches(
            tuple(item.to_model() for item in self.suggestions),
            more=len(self.suggestions) >= limit,
        )
