"""``NamedInvestmentsDto``: ``GET /api/investments?q=&limit=`` [P] (sample
``api.investments_q``), the investments whose name contains a text, across the country."""

from deweloperuch_mcp.api.dto.dto import Dto
from deweloperuch_mcp.models.investment_summary import InvestmentMatches, InvestmentSummary


class NamedInvestmentDto(Dto):
    name: str
    slug: str
    offerCount: int | None = None

    def to_model(self) -> InvestmentSummary:
        # [W] samples api.investments_q and page.investment (both 2026-10-09): `offerCount`
        # is the number of active offers. Seen once: nowy-targowek-vi has offerCount 27 in
        # the first and active_offers 27 (of 75) in the second.
        return InvestmentSummary(
            investment_slug=self.slug, name=self.name, offers_active=self.offerCount
        )


class NamedInvestmentsDto(Dto):
    investments: list[NamedInvestmentDto]
    hasMore: bool = False
    total: int | None = None
    page: int | None = None

    def to_model(self) -> InvestmentMatches:
        # [W] sample api.investments_q (limit=5): `total` and `hasMore` mean what they mean
        # in /api/cities (T27 [P]): every match, and more than given.
        # tests/e2e/test_live_investment_search.py checks both.
        return InvestmentMatches(
            items=tuple(item.to_model() for item in self.investments),
            total=self.total,
            more=self.hasMore,
        )
