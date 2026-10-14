"""``SearchOffersCliPresenter`` (D17 reference): ``offers search`` for people or as JSON."""

from deweloperuch_mcp.consumers.cli.presenters.offer_cli_presenter import OfferCliPresenter
from deweloperuch_mcp.consumers.cli.support.common import show
from deweloperuch_mcp.consumers.cli.support.formatting import number_text
from deweloperuch_mcp.consumers.shared.offer_views import OfferSearchView
from deweloperuch_mcp.models.values import BROWSABLE_PAGES
from deweloperuch_mcp.usecases.search_offers import SearchOffersResult


class SearchOffersCliPresenter(OfferCliPresenter):
    """The page of offers: its view as JSON (``--json``) or as Polish text."""

    def __init__(self, *, as_json: bool) -> None:
        self._as_json = as_json

    def present(self, result: SearchOffersResult) -> None:
        show(OfferSearchView.from_result(result), self._as_json, self._text)

    @classmethod
    def _text(cls, result: OfferSearchView) -> str:
        head = [f"Pasujące oferty: {number_text(result.total)}"]
        if result.pages_available:
            head.append(f"strona {result.page} z {result.pages_available} (po {result.per_page})")
        head.append(f"pokazano {result.returned}")
        if result.truncated:
            head.append(f"obcięte: serwis pozwala przejrzeć najwyżej {BROWSABLE_PAGES} stron")
        lines = [" · ".join(head) + "."]
        if result.hint:
            lines.append(f"Wskazówka: {result.hint}")
        if result.list_url:
            lines.append(f"Ta lista na deweloperuch.pl: {result.list_url}")
        for item in result.items:
            lines.append(cls.offer_line(item))
            where = f"    {item.investment_name} [{item.investment_slug}] · {item.developer_name}"
            lines.append(where + (f" · {item.city}" if item.city else ""))
            if item.investment_url:
                lines.append(f"    {item.investment_url}")
        if result.items:
            lines.append(
                "Szczegóły oferty: deweloperuch offers get OFFER_ID --investment INVESTMENT_SLUG"
            )
        return "\n".join(lines)
