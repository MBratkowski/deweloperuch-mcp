"""The view of an investment: what ``get_investment`` shows, for the CLI (``--json``) and
for the MCP presenter, built from the use case's result (``from_result``). Its offers and
developer are the offers' views (``offer_views``)."""

from typing import Self

from deweloperuch_mcp.consumers.shared.offer_views import Developer, OfferView
from deweloperuch_mcp.consumers.shared.view import View
from deweloperuch_mcp.usecases.get_investment import GetInvestmentResult


class InvestmentView(View):
    """A development project with its developer and offers (``get_investment``)."""

    investment_slug: str
    name: str
    status: str
    """``active`` or ``archived``."""
    investment_url: str | None = None
    """The investment's page on the service (its offers have no pages of their own)."""
    city: str
    city_slug: str
    street: str | None = None
    lat: float | None = None
    lng: float | None = None
    currency: str | None = None
    developer: Developer
    developer_url: str | None = None
    """The developer's profile on the service."""
    avg_price: float | None = None
    """Mean price of the active offers."""
    avg_area_m2: float | None = None
    avg_price_per_m2: float | None = None
    offers_active: int | None = None
    offers_total: int | None = None
    """Active and archived offers, as counted by the service."""
    offers: list[OfferView]
    """Active offers first, then the rest; at most ``limit`` of them."""
    offers_omitted: int
    """Offers left out because of ``limit``."""

    @classmethod
    def from_result(cls, result: GetInvestmentResult) -> Self:
        listing = result.listing
        shown = listing.investment
        return cls(
            investment_slug=shown.investment_slug,
            name=shown.name,
            status=shown.status,
            investment_url=result.investment_url,
            city=shown.city,
            city_slug=shown.city_slug,
            street=shown.street,
            lat=shown.lat,
            lng=shown.lng,
            currency=shown.currency,
            developer=Developer.from_model(shown.developer),
            developer_url=result.developer_url,
            avg_price=shown.avg_price,
            avg_area_m2=shown.avg_area_m2,
            avg_price_per_m2=shown.avg_price_per_m2,
            offers_active=shown.offers_active,
            offers_total=shown.offers_total,
            offers=[OfferView.from_model(offer) for offer in listing.offers],
            offers_omitted=listing.omitted,
        )
