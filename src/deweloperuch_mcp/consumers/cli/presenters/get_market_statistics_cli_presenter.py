"""``GetMarketStatisticsCliPresenter``: ``stats market`` for people or as JSON."""

from deweloperuch_mcp.consumers.cli.support.common import show
from deweloperuch_mcp.consumers.cli.support.formatting import amount_text, number_text
from deweloperuch_mcp.consumers.shared.market_views import MarketStatisticsView, SpreadView
from deweloperuch_mcp.usecases.get_market_statistics import GetMarketStatisticsResult


class GetMarketStatisticsCliPresenter:
    """The summary: its view as JSON (``--json``) or as Polish text."""

    def __init__(self, *, as_json: bool) -> None:
        self._as_json = as_json

    def present(self, result: GetMarketStatisticsResult) -> None:
        show(MarketStatisticsView.from_result(result), self._as_json, self._text)

    @classmethod
    def _text(cls, result: MarketStatisticsView) -> str:
        """Head lines, a table of the spreads, then the largest developers."""
        lines = [
            f"Rynek ofert [{result.city_slug}] · aktywne oferty: {number_text(result.offers)} · "
            f"inwestycje: {number_text(result.investments)} · deweloperzy: "
            f"{number_text(result.developers)}."
        ]
        if result.hint:
            lines.append(f"Wskazówka: {result.hint}")
        if result.list_url:
            lines.append(f"Te oferty na deweloperuch.pl: {result.list_url}")
        lines += cls._spread_lines(result)
        if result.top_developers:
            lines.append(
                f"Najwięcej ofert (pokazano {len(result.top_developers)} z {result.developers}):"
            )
            for share in result.top_developers:
                lines.append(
                    f"  {share.developer_slug} · oferty {number_text(share.offers)} · inwestycje "
                    f"{number_text(share.investments)} · mediana "
                    f"{amount_text(share.median_price_per_m2, 'PLN/m²')}"
                )
                if share.developer_url:
                    lines.append(f"      {share.developer_url}")
        return "\n".join(lines)

    @classmethod
    def _spread_lines(cls, result: MarketStatisticsView) -> list[str]:
        """The spreads of prices, prices per m² and areas as a table; none without them."""
        spreads = [
            ("Cena (PLN)", result.price, 0),
            ("Cena za m² (PLN)", result.price_per_m2, 0),
            ("Metraż (m²)", result.area_m2, 2),
        ]
        rows = [
            [label, *(number_text(value, digits) for value in cls._values(spread))]
            for label, spread, digits in spreads
            if spread is not None
        ]
        if not rows:
            return []
        header = ["", "min", "p25", "mediana", "p75", "max"]
        widths = [max(len(row[i]) for row in [header, *rows]) for i in range(len(header))]
        lines = []
        for row in [header, *rows]:
            cells = [row[0].ljust(widths[0])]
            cells += [cell.rjust(width) for cell, width in zip(row[1:], widths[1:], strict=True)]
            lines.append("  ".join(cells).rstrip())
        return lines

    @staticmethod
    def _values(spread: SpreadView) -> list[float]:
        return [spread.min, spread.p25, spread.median, spread.p75, spread.max]
