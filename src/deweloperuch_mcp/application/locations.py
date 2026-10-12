"""Use case: find cities, districts and streets by a part of their name."""

from deweloperuch_mcp.application.failures import reported_as
from deweloperuch_mcp.domain.locations import LocationSearchResult
from deweloperuch_mcp.domain.ports import LocationDirectory
from deweloperuch_mcp.domain.values import LocationQuery


class SearchLocations:
    """Cities first (with their offer counts), then districts and streets; the result
    says when more may match (D4). Its ``city_slug`` goes to an offers search."""

    def __init__(self, directory: LocationDirectory) -> None:
        self._directory = directory

    def __call__(self, query: LocationQuery) -> LocationSearchResult:
        with reported_as("Wyszukiwanie miast"):
            cities = self._directory.cities(query)
        with reported_as("Wyszukiwanie dzielnic i ulic"):
            places = self._directory.districts_and_streets(query)
        return LocationSearchResult.of(query, cities, places)
