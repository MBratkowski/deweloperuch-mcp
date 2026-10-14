"""``GetTransactionStatisticsCliPresenter``: ``stats transactions`` for people or as JSON
(``--json``: the whole view, every measure, averages included)."""

from collections.abc import Callable

from deweloperuch_mcp.consumers.cli.support.common import show
from deweloperuch_mcp.consumers.cli.support.formatting import cell_text, number_text
from deweloperuch_mcp.consumers.shared.transaction_views import (
    TransactionPeriodView,
    TransactionStatisticsView,
)
from deweloperuch_mcp.usecases.get_transaction_statistics import GetTransactionStatisticsResult

Measure = Callable[[TransactionPeriodView], float | None]

# The columns of the text, in this order; a column without any value is left out (the
# quarters have only the average price of one m²). The averages of area and price are
# in ``--json``.
_COLUMNS: tuple[tuple[str, Measure], ...] = (
    ("Mediana PLN/m²", lambda item: item.median_price_per_m2),
    ("Średnia PLN/m²", lambda item: item.average_price_per_m2),
    ("Mediana m²", lambda item: item.median_area_m2),
    ("Mediana ceny PLN", lambda item: item.median_price),
)


class GetTransactionStatisticsCliPresenter:
    """The statistics: their view as JSON (``--json``) or as Polish text."""

    def __init__(self, *, as_json: bool) -> None:
        self._as_json = as_json

    def present(self, result: GetTransactionStatisticsResult) -> None:
        show(TransactionStatisticsView.from_result(result), self._as_json, self._text)

    @staticmethod
    def _text(result: TransactionStatisticsView) -> str:
        """Head lines, then one row per period: the count and the measures it has."""
        lines = [
            f"Ceny transakcyjne mieszkań (RCN) · {result.city_slug} · "
            f"{result.granularity.frequency.polish}",
            f"Okresy: pokazano {result.returned} z {result.total} "
            f"(dane od {result.available_from}).",
        ]
        if result.hint:
            lines.append(f"Wskazówka: {result.hint}")
        lines.append(f"Uwaga: {result.note}")
        if result.stats_url:
            lines.append(f"Strona na deweloperuch.pl: {result.stats_url}")
        columns = [
            (title, measure)
            for title, measure in _COLUMNS
            if any(measure(item) is not None for item in result.periods)
        ]
        header = ["Okres", "Transakcje", *(title for title, _ in columns)]
        rows = [
            [
                item.period,
                number_text(item.transactions),
                *(cell_text(measure(item)) for _, measure in columns),
            ]
            for item in result.periods
        ]
        widths = [max(len(row[column]) for row in [header, *rows]) for column in range(len(header))]
        for row in [header, *rows]:
            cells = [row[0].ljust(widths[0])]
            cells += [cell.rjust(width) for cell, width in zip(row[1:], widths[1:], strict=True)]
            lines.append("  ".join(cells))
        return "\n".join(lines)
