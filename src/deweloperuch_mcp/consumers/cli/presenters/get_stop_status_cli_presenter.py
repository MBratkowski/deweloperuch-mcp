"""``GetStopStatusCliPresenter``: ``stop status`` for people or as JSON. The text may show
times, sources and how to lift the STOP: it is for people."""

import json
import math

import typer

from deweloperuch_mcp.bootstrap import StopRecord, StopState, UnreadableStop, format_time
from deweloperuch_mcp.consumers.shared.text import printable
from deweloperuch_mcp.usecases.get_stop_status import GetStopStatusResult


class GetStopStatusCliPresenter:
    """The state of the STOP record: as JSON (``--json``) or as Polish text."""

    def __init__(self, *, as_json: bool) -> None:
        self._as_json = as_json

    def present(self, result: GetStopStatusResult[StopState]) -> None:
        state = result.state
        if self._as_json:
            typer.echo(json.dumps(state.to_json(), ensure_ascii=False, indent=2))
        else:
            typer.echo(self._text(state))

    @classmethod
    def _text(cls, state: StopState) -> str:
        stop = state.stop
        if stop is None:
            lines = ["Brak STOP: zapytania do deweloperuch.pl nie są wstrzymane."]
        elif isinstance(stop, UnreadableStop):
            lines = [
                "STOP aktywny bezterminowo: zapis jest nieczytelny.",
                f"Problem: {printable(stop.problem)}",
            ]
        elif state.active:
            lines = [f"STOP aktywny: {stop.label}.", cls._origin(stop)]
            if stop.until is None:
                lines.append("Wygasa: nie, trwa do zdjęcia.")
            else:
                left = max(1, math.ceil(state.seconds_left or 0))
                lines.append(f"Wygasa: {format_time(stop.until)} (za {left} s).")
        else:
            until = "" if stop.until is None else f" {format_time(stop.until)}"
            lines = [
                f"STOP wygasł{until}: {stop.label}.",
                cls._origin(stop),
                "Zapytania do deweloperuch.pl nie są wstrzymane.",
            ]
        if state.active:
            lines.append(
                "Blokadę zdejmuje użytkownik po sprawdzeniu przyczyny: deweloperuch stop clear"
            )
        lines.append(f"Plik: {printable(str(state.path))}")
        return "\n".join(lines)

    @staticmethod
    def _origin(stop: StopRecord) -> str:
        pid = "" if stop.pid is None else f" (PID {stop.pid})"
        return f"Od: {format_time(stop.since)} · źródło: {stop.source}{pid}"
