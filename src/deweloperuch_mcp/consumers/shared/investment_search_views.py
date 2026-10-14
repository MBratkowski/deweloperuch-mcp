"""The views of an investments search: what ``search_investments`` shows, for the CLI
(``--json``) and for the MCP presenter (the domain's names, ``None`` for what is not
known, links in ``*_url`` fields). Each builds itself from the use case's result
(``from_result``) or a model (``from_model``).
"""

from typing import Self

from deweloperuch_mcp.consumers.shared.view import View
from deweloperuch_mcp.models.investment_summary import InvestmentSummary
from deweloperuch_mcp.usecases.search_investments import SearchInvestmentsResult


class InvestmentSummaryView(View):
    """An investment in the results of ``search_investments``. A search by name knows
    only ``investment_slug``, ``name`` and ``offers_active``."""

    investment_slug: str
    name: str
    status: str | None = None
    """``active`` or ``archived``."""
    investment_url: str | None = None
    """The investment's page on the service."""
    city: str | None = None
    city_slug: str | None = None
    district: str | None = None
    street: str | None = None
    lat: float | None = None
    lng: float | None = None
    developer_slug: str | None = None
    developer_name: str | None = None
    developer_url: str | None = None
    """The developer's profile on the service."""
    avg_price: float | None = None
    """Mean price of the active offers, in PLN."""
    avg_area_m2: float | None = None
    avg_price_per_m2: float | None = None
    offers_active: int | None = None
    offers_total: int | None = None
    """Active and archived offers, as counted by the service."""

    @classmethod
    def from_model(
        cls, item: InvestmentSummary, investment_url: str | None, developer_url: str | None
    ) -> Self:
        developer = item.developer
        return cls(
            investment_slug=item.investment_slug,
            name=item.name,
            status=item.status,
            investment_url=investment_url,
            city=item.city,
            city_slug=item.city_slug,
            district=item.district,
            street=item.street,
            lat=item.lat,
            lng=item.lng,
            developer_slug=None if developer is None else developer.developer_slug,
            developer_name=None if developer is None else developer.name,
            developer_url=developer_url,
            avg_price=item.avg_price,
            avg_area_m2=item.avg_area_m2,
            avg_price_per_m2=item.avg_price_per_m2,
            offers_active=item.offers_active,
            offers_total=item.offers_total,
        )


class InvestmentSearchView(View):
    """The investments ``search_investments`` shows (D4: the cut is explicit)."""

    total: int | None
    """All matching; ``None`` when the service does not say (a search by name)."""
    returned: int
    truncated: bool
    """More investments match than shown."""
    hint: str | None = None
    items: list[InvestmentSummaryView]

    @classmethod
    def from_result(cls, found: SearchInvestmentsResult) -> Self:
        search = found.search
        return cls(
            total=search.total,
            returned=search.returned,
            truncated=search.truncated,
            hint=found.hint,
            items=[
                InvestmentSummaryView.from_model(item, investment_url, developer_url)
                for item, investment_url, developer_url in zip(
                    search.items, found.investment_urls, found.developer_urls, strict=True
                )
            ],
        )
