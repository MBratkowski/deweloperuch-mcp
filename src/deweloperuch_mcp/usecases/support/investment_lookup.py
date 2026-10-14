"""``InvestmentLookup``: an investment by its slug, for every use case that needs one
(``GetOffer``, ``GetInvestment``), with one wording of "not found" (D12)."""

from deweloperuch_mcp.models.investment import Investment
from deweloperuch_mcp.models.values import InvestmentSlug
from deweloperuch_mcp.usecases.ports import InvestmentCatalog
from deweloperuch_mcp.usecases.support.failures import ReportedAs


class InvestmentLookup:
    """The investments of ``catalog``; an unknown slug is a ``NotFoundError`` that says
    where slugs come from."""

    def __init__(self, catalog: InvestmentCatalog) -> None:
        self._catalog = catalog

    def investment(self, slug: InvestmentSlug) -> Investment:
        with ReportedAs(
            f"Inwestycja {slug.value!r}",
            not_found=(
                f"Nie znaleziono inwestycji {slug.value!r}. Slug inwestycji podaje "
                "search_investments, search_offers albo get_developer (pole investment_slug)."
            ),
        ):
            return self._catalog.investment(slug)
