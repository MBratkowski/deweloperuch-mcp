"""Use case ``SearchDevelopers``: developers by a part of their name, with the link to each
profile."""

from dataclasses import dataclass
from typing import Self

from deweloperuch_mcp.models.developer_match import (
    DEFAULT_MATCHES,
    MAX_MATCHES,
    DeveloperName,
    DeveloperSearchResult,
    MatchCount,
)
from deweloperuch_mcp.models.values import WHOLE_COUNTRY, CitySlug
from deweloperuch_mcp.usecases.ports import DeveloperLinks, DeveloperSearch
from deweloperuch_mcp.usecases.support.arguments import ParameterCheck
from deweloperuch_mcp.usecases.support.failures import ReportedAs


@dataclass(frozen=True, kw_only=True)
class SearchDevelopersRequest:
    """A part of the name and how many developers to show, checked (``parse``) before
    anything is sent."""

    name: DeveloperName
    limit: MatchCount

    @classmethod
    def parse(cls, *, name: object, limit: object = DEFAULT_MATCHES) -> Self:
        """Checked in this order: name, limit. A refusal names the parameter
        (``InvalidInputError``)."""
        with ParameterCheck():
            return cls(name=DeveloperName.parse(name), limit=MatchCount.parse(limit))


@dataclass(frozen=True, kw_only=True)
class SearchDevelopersResult:
    """The developers found (``search``) and the profile page of each (D12, aligned with
    ``search.items``)."""

    search: DeveloperSearchResult
    developer_urls: tuple[str | None, ...]

    @property
    def hint(self) -> str | None:
        """What to do about a search that does not show every match (D4) or matches
        nothing; ``None`` otherwise."""
        search = self.search
        if search.truncated:
            if search.total is None:
                shown = f"Pokazano {search.returned} pasujących deweloperów, a może ich być więcej."
            else:
                shown = f"Pokazano {search.returned} z {search.total} pasujących deweloperów."
            if search.count.value < MAX_MATCHES:
                return f"{shown} Doprecyzuj nazwę albo zwiększ limit (najwyżej {MAX_MATCHES})."
            return f"{shown} Doprecyzuj nazwę."
        if not search.items:
            return (
                f"Żaden deweloper nie pasuje do {search.name.text!r}. Sprawdź pisownię albo "
                "podaj krótszy fragment nazwy, np. jej pierwsze słowo."
            )
        return None


class SearchDevelopers:
    """At most ``limit`` developers whose name matches, with the link to each profile.

    The service's matches carry no city, so the profiles are those of the whole country
    (``polska``).
    """

    def __init__(self, directory: DeveloperSearch, links: DeveloperLinks) -> None:
        self._directory = directory
        self._links = links

    def execute(self, request: SearchDevelopersRequest) -> SearchDevelopersResult:
        with ReportedAs("Wyszukiwanie deweloperów"):
            matches = self._directory.developers(request.name, request.limit)
        search = DeveloperSearchResult.of(request.name, request.limit, matches)
        country = CitySlug(WHOLE_COUNTRY)
        return SearchDevelopersResult(
            search=search,
            developer_urls=tuple(
                self._links.developer_profile(item.developer_slug, country) for item in search.items
            ),
        )
