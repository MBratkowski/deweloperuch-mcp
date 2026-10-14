"""``DevelopersDto``: ``GET /api/developers?q=&limit=`` [P] (sample ``api.developers_q``),
the developers whose name matches."""

from deweloperuch_mcp.api.dto.dto import Dto
from deweloperuch_mcp.models.developer_match import DeveloperMatch, DeveloperMatches


class DeveloperFoundDto(Dto):
    name: str
    slug: str
    offerCount: int | None = None

    def to_model(self) -> DeveloperMatch:
        # [W] ``offerCount`` counts the developer's offers: for ATAL it equals ``totalSales``
        # of the developers list (4265, samples api.developers_q and page.developers_list,
        # both 2026-10-09); whether archived offers count is not known.
        return DeveloperMatch(developer_slug=self.slug, name=self.name, offer_count=self.offerCount)


class DevelopersDto(Dto):
    """``hasMore`` and ``total`` decide whether a result is cut (D4), so they are required."""

    developers: list[DeveloperFoundDto]
    hasMore: bool
    total: int
    page: int | None = None

    def to_model(self) -> DeveloperMatches:
        # [W] docs/discovery/endpoints.md, /api/developers: ``total`` (every match) and
        # ``hasMore`` (more than given) are read as /api/cities has them (T27,
        # [P 2026-10-10]); here they were seen only as total 1, hasMore false.
        return DeveloperMatches(
            tuple(item.to_model() for item in self.developers),
            total=self.total,
            more=self.hasMore,
        )
