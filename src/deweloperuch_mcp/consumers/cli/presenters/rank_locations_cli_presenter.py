"""``RankLocationsCliPresenter``: ``stats cities`` for people or as JSON (``--json``: the
view, ``consumers.shared.ranking_views``)."""

from deweloperuch_mcp.consumers.cli.support.common import show

# The Polish way of writing numbers, shared with the other commands' text.
from deweloperuch_mcp.consumers.cli.support.formatting import amount_text, number_text
from deweloperuch_mcp.consumers.shared.ranking_views import LocationRankingView, RankedLocationView
from deweloperuch_mcp.consumers.shared.text import printable
from deweloperuch_mcp.usecases.rank_locations import RankLocationsResult

_LEVELS = {"city": "miejscowości", "powiat": "powiatów"}
_ORDERS = {
    "transactions_desc": "wg liczby transakcji",
    "price_per_m2_desc": "od najwyższej ceny za m²",
    "price_per_m2_asc": "od najniższej ceny za m²",
}
# [H] T10: the period and whether the service's figures are averages or medians.
CAVEAT = "Serwis nie podaje okresu ani tego, czy ceny i metraż to średnie, czy mediany."


class RankLocationsCliPresenter:
    """The ranking: its view as JSON (``--json``) or as Polish text."""

    def __init__(self, *, as_json: bool) -> None:
        self._as_json = as_json

    def present(self, result: RankLocationsResult) -> None:
        show(LocationRankingView.from_result(result), self._as_json, self._text)

    @classmethod
    def _text(cls, result: LocationRankingView) -> str:
        head = (
            f"Ranking {_LEVELS.get(result.level, result.level)} "
            f"{_ORDERS.get(result.sort, result.sort)}: pokazano {result.returned} z "
            f"{number_text(result.total)}"
        )
        if result.min_transactions:
            head += f" (co najmniej {number_text(result.min_transactions)} transakcji)"
        lines = [head + "."]
        if result.hint:
            lines.append(f"Wskazówka: {result.hint}")
        if result.ranking_url:
            lines.append(f"Ranking miast na deweloperuch.pl: {result.ranking_url}")
        width = len(str(len(result.items)))
        for position, item in enumerate(result.items, start=1):
            lines.append(f"{position:>{width}}. {cls._place(item)}")
        if result.items:
            lines.append(CAVEAT)
        return "\n".join(lines)

    @staticmethod
    def _place(item: RankedLocationView) -> str:
        if item.city_slug:
            name = f"{printable(item.name)} [{printable(item.city_slug)}]"
        elif item.powiat_id is not None:
            name = f"{printable(item.name)} [id {item.powiat_id}]"
        else:
            name = printable(item.name)
        return " · ".join(
            [
                name,
                f"transakcji: {number_text(item.transaction_count)}",
                amount_text(item.price_per_m2, "PLN/m²"),
                amount_text(item.area_m2, "m²", 2),
                amount_text(item.price, "PLN"),
            ]
        )
