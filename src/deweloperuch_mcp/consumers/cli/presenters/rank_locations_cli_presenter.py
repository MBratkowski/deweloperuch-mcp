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
    "value_desc": "od najwyższej wartości",
    "value_asc": "od najniższej wartości",
}
_MARKETS = {"secondary": "rynek wtórny", "primary": "rynek pierwotny", "all": "oba rynki"}
_INDICATORS = {
    "unemployment_rate": "stopa bezrobocia rejestrowanego",
    "average_wage": "przeciętne miesięczne wynagrodzenie brutto, średnia za rok",
    "dwellings_completed": "mieszkania oddane w 12 miesiącach do miesiąca",
    "dwellings_started": "mieszkania rozpoczęte w 12 miesiącach do miesiąca",
    "average_dwelling_area": "powierzchnia mieszkania podana przez serwis",
    "natural_increase": "przyrost naturalny",
    "nbp_price_per_m2": "cena transakcyjna rynku wtórnego wg NBP",
}
# [H] T10: the period and whether the service's figures are averages or medians.
CAVEAT = "Serwis nie podaje okresu ani tego, czy ceny i metraż to średnie, czy mediany."
# [H] T85: the powiats' figures name their period, not whether they are medians.
POWIAT_CAVEAT = "Serwis nie podaje, czy ceny i metraż to średnie, czy mediany."


class RankLocationsCliPresenter:
    """The ranking: its view as JSON (``--json``) or as Polish text."""

    def __init__(self, *, as_json: bool) -> None:
        self._as_json = as_json

    def present(self, result: RankLocationsResult) -> None:
        show(LocationRankingView.from_result(result), self._as_json, self._text)

    @classmethod
    def _text(cls, result: LocationRankingView) -> str:
        lines = [cls._head(result) + "."]
        if result.hint:
            lines.append(f"Wskazówka: {result.hint}")
        if result.ranking_url:
            lines.append(f"Ranking miast na deweloperuch.pl: {result.ranking_url}")
        width = len(str(len(result.items)))
        for position, item in enumerate(result.items, start=1):
            lines.append(f"{position:>{width}}. {cls._place(item, result.unit)}")
        if result.items and result.indicator is None:
            lines.append(POWIAT_CAVEAT if result.level == "powiat" else CAVEAT)
        return "\n".join(lines)

    @staticmethod
    def _head(result: LocationRankingView) -> str:
        order = _ORDERS.get(result.sort, result.sort)
        shown = f"pokazano {result.returned} z {number_text(result.total)}"
        if result.indicator is not None:
            name = _INDICATORS.get(result.indicator, result.indicator)
            period = result.period or "okres nieznany"
            return f"Ranking miast wg wskaźnika: {name} ({period}), {order}: {shown}"
        head = f"Ranking {_LEVELS.get(result.level, result.level)} {order}"
        if result.market is not None:
            head += f" ({_MARKETS.get(result.market, result.market)}"
            if result.period_start and result.period_end:
                head += f", {result.period_start[:7]}–{result.period_end}"
            head += ")"
        head += f": {shown}"
        if result.min_transactions:
            head += f" (co najmniej {number_text(result.min_transactions)} transakcji)"
        return head

    @staticmethod
    def _place(item: RankedLocationView, unit: str | None) -> str:
        if item.city_slug:
            name = f"{printable(item.name)} [{printable(item.city_slug)}]"
        elif item.powiat_id is not None:
            name = f"{printable(item.name)} [id {item.powiat_id}]"
        else:
            name = printable(item.name)
        if unit is not None:
            return f"{name} · {amount_text(item.value, unit, 2)}"
        return " · ".join(
            [
                name,
                f"transakcji: {number_text(item.transaction_count or 0)}",
                amount_text(item.price_per_m2, "PLN/m²"),
                amount_text(item.area_m2, "m²", 2),
                amount_text(item.price, "PLN"),
            ]
        )
