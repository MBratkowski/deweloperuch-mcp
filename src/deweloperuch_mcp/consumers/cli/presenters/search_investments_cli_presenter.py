"""``SearchInvestmentsCliPresenter``: ``investments search`` for people or as JSON."""

from deweloperuch_mcp.consumers.cli.support.common import show
from deweloperuch_mcp.consumers.cli.support.formatting import (
    amount_text,
    count_text,
    number_text,
    status_text,
)
from deweloperuch_mcp.consumers.shared.investment_search_views import (
    InvestmentSearchView,
    InvestmentSummaryView,
)
from deweloperuch_mcp.usecases.search_investments import SearchInvestmentsResult


class SearchInvestmentsCliPresenter:
    """The investments found: their view as JSON (``--json``) or as Polish text."""

    def __init__(self, *, as_json: bool) -> None:
        self._as_json = as_json

    def present(self, result: SearchInvestmentsResult) -> None:
        larger_limit = result.search.larger_limit_shows_more
        show(
            InvestmentSearchView.from_result(result),
            self._as_json,
            lambda view: self._text(view, larger_limit=larger_limit),
        )

    @classmethod
    def _text(cls, result: InvestmentSearchView, *, larger_limit: bool) -> str:
        """A head line, then three or four lines per investment (what the search knows).

        ``larger_limit``: a larger ``--limit`` would show more (a search by name never
        shows more than 50), so the head suggests it.
        """
        if result.total is None:
            head = f"Inwestycje: pokazano {result.returned}, może być więcej."
        else:
            head = f"Inwestycje: {number_text(result.total)} · pokazano {result.returned}"
            if larger_limit:
                head += " (zwiększ --limit albo zawęź wyniki)."
            else:
                head += " (zawęź wyniki)." if result.truncated else "."
        lines = [head]
        if result.hint:
            lines.append(f"Wskazówka: {result.hint}")
        for item in result.items:
            lines += cls._investment_lines(item)
        if result.items:
            lines.append("Oferty inwestycji: deweloperuch investments get INVESTMENT_SLUG")
        return "\n".join(lines)

    @staticmethod
    def _investment_lines(item: InvestmentSummaryView) -> list[str]:
        head = [f"{item.name} [{item.investment_slug}]"]
        if item.status:
            head.append(status_text(item.status))
        place = ", ".join(part for part in (item.city, item.district, item.street) if part)
        if place:
            head.append(place)
        offers = f"oferty: aktywne {count_text(item.offers_active)}"
        if item.offers_total is not None:
            offers += f" z {number_text(item.offers_total)}"
        details = [offers]
        if item.avg_price is not None or item.avg_price_per_m2 is not None:
            details.append(
                "średnio "
                + " · ".join(
                    [
                        amount_text(item.avg_price, "PLN"),
                        amount_text(item.avg_area_m2, "m²", 2),
                        amount_text(item.avg_price_per_m2, "PLN/m²", 2),
                    ]
                )
            )
        lines = [" · ".join(head), "    " + " · ".join(details)]
        if item.developer_name:
            lines.append(f"    {item.developer_name} [{item.developer_slug}]")
        if item.investment_url:
            lines.append(f"    {item.investment_url}")
        return lines
