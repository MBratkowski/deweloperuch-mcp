"""``DeveloperSearch`` and ``DeveloperLinks`` in memory, and the developer they find."""

from typing import TYPE_CHECKING

from deweloperuch_mcp.models.developer_match import (
    DeveloperMatch,
    DeveloperMatches,
    DeveloperName,
    MatchCount,
)
from deweloperuch_mcp.models.values import CitySlug
from deweloperuch_mcp.usecases import ports

ATAL = DeveloperMatch(developer_slug="atal", name="ATAL S.A.", offer_count=4265)


class FakeDeveloperSearch:
    def __init__(
        self, found: DeveloperMatches | None = None, error: Exception | None = None
    ) -> None:
        self.found = found or DeveloperMatches((ATAL,), total=1, more=False)
        self.error = error
        self.calls: list[tuple[DeveloperName, MatchCount]] = []

    def developers(self, name: DeveloperName, count: MatchCount) -> DeveloperMatches:
        self.calls.append((name, count))
        if self.error is not None:
            raise self.error
        return self.found


class FakeDeveloperLinks:
    def __init__(self) -> None:
        self.calls: list[tuple[str, CitySlug]] = []

    def developer_profile(self, developer_slug: str, city: CitySlug) -> str | None:
        self.calls.append((developer_slug, city))
        return f"profile:{city.value}/{developer_slug}"


if TYPE_CHECKING:  # mypy checks that each fake is the port it stands in for
    _developer_search: ports.DeveloperSearch = FakeDeveloperSearch()
    _developer_links: ports.DeveloperLinks = FakeDeveloperLinks()
