"""``ClearStopCliPresenter``: ``stop clear`` for people (no JSON): what was removed."""

import typer

from deweloperuch_mcp.bootstrap import StopState, UnreadableStop
from deweloperuch_mcp.consumers.shared.text import printable
from deweloperuch_mcp.usecases.clear_stop import ClearStopResult


class ClearStopCliPresenter:
    """What the STOP record held before it was removed, as Polish text."""

    def present(self, result: ClearStopResult[StopState]) -> None:
        typer.echo(self._text(result.before))

    @staticmethod
    def _text(before: StopState) -> str:
        stop = before.stop
        if stop is None:
            return "Brak STOP: nie było czego zdejmować."
        if isinstance(stop, UnreadableStop):
            lines = [f"Zdjęto nieczytelny zapis STOP ({printable(stop.problem)})."]
        else:
            expired = "" if before.active else " (już wygasł)"
            lines = [f"Zdjęto STOP{expired}: {stop.summary()}."]
            if before.active and stop.until is not None:
                lines.append("Pauza po 429 zapisana w limiterze nadal obowiązuje.")
        lines.append(
            "Działający serwer MCP, który trafił na STOP, wyśle zapytania dopiero po ponownym "
            "uruchomieniu."
        )
        return "\n".join(lines)
