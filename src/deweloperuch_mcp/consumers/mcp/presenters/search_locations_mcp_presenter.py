"""``SearchLocationsMcpPresenter``: ``search_locations``' result for a model, and its output
schema (``LocationsResult``)."""

from pydantic import Field

from deweloperuch_mcp.consumers.mcp.support.mcp_model import McpModel
from deweloperuch_mcp.consumers.shared.location_views import LocationSearchView
from deweloperuch_mcp.usecases.search_locations import SearchLocationsResult

# [W] docs/discovery/endpoints.md, location-search: `count` of districts and streets is
# the number of offers; hence "przybliżona".
OFFER_COUNT = "Liczba ofert wg serwisu (dla dzielnic i ulic przybliżona; 0 = brak ofert)."

# Class docstrings would become schema descriptions for the model: comments instead.


class LocationItem(McpModel):
    kind: str = Field(description="city, district albo street.")
    name: str
    city: str
    city_slug: str
    district: str | None = None
    street: str | None = None
    lat: float | None = None
    lng: float | None = None
    offer_count: int | None = Field(None, description=OFFER_COUNT)


class LocationsResult(McpModel):
    keep_null = frozenset({"total"})  # D4: always there, null when unknown

    total: int | None = Field(
        description="Wszystkie pasujące; null, gdy wyników jest więcej niż pokazano."
    )
    returned: int
    truncated: bool
    hint: str | None = None
    items: list[LocationItem]


class SearchLocationsMcpPresenter:
    """The locations as their view has them; ``dump`` leaves out ``null`` but ``total``."""

    def present(self, result: SearchLocationsResult) -> LocationsResult:
        return LocationsResult.model_validate(LocationSearchView.from_result(result).model_dump())
