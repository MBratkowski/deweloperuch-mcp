"""Use case ``SearchLocations``: cities, districts and streets by a part of their name."""

from dataclasses import dataclass
from typing import Self

from deweloperuch_mcp.models.location import LocationSearchResult
from deweloperuch_mcp.models.values import LocationQuery
from deweloperuch_mcp.usecases.ports import LocationDirectory
from deweloperuch_mcp.usecases.support.arguments import ParameterCheck
from deweloperuch_mcp.usecases.support.failures import ReportedAs


@dataclass(frozen=True, kw_only=True)
class SearchLocationsRequest:
    """The part of a name to look for, checked (``parse``) before anything is sent."""

    query: LocationQuery

    @classmethod
    def parse(cls, *, query: object) -> Self:
        """A refusal names the parameter (``InvalidInputError``)."""
        with ParameterCheck():
            return cls(query=LocationQuery.parse(query))


@dataclass(frozen=True, kw_only=True)
class SearchLocationsResult:
    """The locations that match, cities first, and whether more may match (D4)."""

    found: LocationSearchResult


class SearchLocations:
    """Cities first (with their offer counts), then districts and streets; the result
    says when more may match (D4). Its ``city_slug`` goes to an offers search."""

    def __init__(self, directory: LocationDirectory) -> None:
        self._directory = directory

    def execute(self, request: SearchLocationsRequest) -> SearchLocationsResult:
        query = request.query
        with ReportedAs("Wyszukiwanie miast"):
            cities = self._directory.cities(query)
        with ReportedAs("Wyszukiwanie dzielnic i ulic"):
            places = self._directory.districts_and_streets(query)
        return SearchLocationsResult(found=LocationSearchResult.of(query, cities, places))
