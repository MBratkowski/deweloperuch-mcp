"""``CitiesDto``: ``GET /api/cities?q=&limit=`` [P] (sample ``api.cities_q``), the cities
whose name contains a query, with their offer counts."""

from pydantic import Field

from deweloperuch_mcp.api.dto.dto import Dto
from deweloperuch_mcp.models.location import Location, LocationMatches


class CityMappingDto(Dto):
    city: str
    city_slug: str
    offerCount: int

    def to_model(self) -> Location:
        return Location.city_of(
            name=self.city, city_slug=self.city_slug, offer_count=self.offerCount
        )


class CitiesDto(Dto):
    cities: list[str] = Field(default_factory=list)
    cityMappings: list[CityMappingDto]
    hasMore: bool = False
    total: int | None = None
    page: int | None = None

    def to_model(self) -> LocationMatches:
        # [W] docs/discovery/endpoints.md, /api/cities: `hasMore` is in the response, but
        # its meaning is a conclusion (pagination is [H], `hasMore: true` never seen).
        return LocationMatches(
            tuple(city.to_model() for city in self.cityMappings), more=self.hasMore
        )
