"""``CityDistrictsDto``: ``GET /api/city-districts?citySlug=`` [P] (docs/discovery/endpoints.md,
sample ``api.city_districts.offers_v2``), the districts of a city in which the service has
offers."""

from typing import Annotated

from pydantic import StringConstraints

from deweloperuch_mcp.api.dto.dto import Dto
from deweloperuch_mcp.models.district import District
from deweloperuch_mcp.models.values import DISTRICT_MAX, DISTRICT_MIN

ListSlug = Annotated[
    str,
    StringConstraints(
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", min_length=DISTRICT_MIN, max_length=DISTRICT_MAX
    ),
]
"""[P 2026-10-30] endpoints.md, city-districts: a slug is ASCII ``[a-z0-9-]``. The search sends
it back as a district, whose slug it stays (``api.queries.offers_query``), so one outside
these bounds is off the contract."""


class CityDistrictDto(Dto):
    """``count`` is not read: it only orders the list and is not an official number of
    offers (endpoints.md, city-districts)."""

    name: str
    slug: ListSlug

    def to_model(self) -> District:
        return District(name=self.name, slug=self.slug)


class CityDistrictsDto(Dto):
    """[P 2026-11-01] the offers variant (no ``variant``): ``{districts: [{name, slug, count}]}``,
    sorted by ``count``, largest first."""

    districts: list[CityDistrictDto]

    def to_model(self) -> tuple[District, ...]:
        """The districts in the service's order."""
        return tuple(row.to_model() for row in self.districts)
