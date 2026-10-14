"""``GetGovernmentStatisticsCliPresenter``: ``stats government`` for people or as JSON."""

import dataclasses
import json

import typer

from deweloperuch_mcp.consumers.cli.support.formatting import cell_text
from deweloperuch_mcp.consumers.shared.government_statistics_views import (
    GovernmentStatisticsView,
)
from deweloperuch_mcp.usecases.get_government_statistics import GetGovernmentStatisticsResult


class GetGovernmentStatisticsCliPresenter:
    """The statistics: their view's dataclasses as JSON (``--json``) or Polish text with
    the series as a table."""

    def __init__(self, *, as_json: bool) -> None:
        self._as_json = as_json

    def present(self, result: GetGovernmentStatisticsResult) -> None:
        view = GovernmentStatisticsView.from_result(result)
        if self._as_json:
            typer.echo(json.dumps(dataclasses.asdict(view), ensure_ascii=False, indent=2))
        else:
            typer.echo(self._text(view))

    @classmethod
    def _text(cls, result: GovernmentStatisticsView) -> str:
        """Head lines, the series as numbered columns, then one row per period."""
        lines = [
            f"{result.title} · {result.location_name} [{result.location_slug}]",
            f"Źródło: {result.source} · {result.frequency.polish} · okresy: pokazano "
            f"{result.returned} z {result.total} (dane od {result.available_from}).",
        ]
        if result.hint:
            lines.append(f"Wskazówka: {result.hint}")
        if result.note:
            lines.append(f"Uwaga: {result.note}")
        if result.stats_url:
            lines.append(f"Strona na deweloperuch.pl: {result.stats_url}")
        lines.append("Kolumny:")
        lines += [
            f"  [{index}] {series.label} ({series.unit})"
            for index, series in enumerate(result.series, start=1)
        ]
        return "\n".join(lines + cls._table(result))

    @staticmethod
    def _table(result: GovernmentStatisticsView) -> list[str]:
        """A header row, then one row per period: its label and each series' value."""
        header = ["Okres", *(f"[{index}]" for index in range(1, len(result.series) + 1))]
        rows = [
            [period, *(cell_text(series.points[index].value) for series in result.series)]
            for index, period in enumerate(result.periods)
        ]
        widths = [max(len(row[column]) for row in [header, *rows]) for column in range(len(header))]
        lines = []
        for row in [header, *rows]:
            cells = [row[0].ljust(widths[0])]
            cells += [cell.rjust(width) for cell, width in zip(row[1:], widths[1:], strict=True)]
            lines.append("  ".join(cells))
        return lines
