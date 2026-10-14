"""``SearchDevelopersCliPresenter``: ``developers search`` for people or as JSON."""

from deweloperuch_mcp.consumers.cli.support.common import show
from deweloperuch_mcp.consumers.cli.support.formatting import number_text
from deweloperuch_mcp.consumers.shared.developer_views import DeveloperSearchView
from deweloperuch_mcp.usecases.search_developers import SearchDevelopersResult


class SearchDevelopersCliPresenter:
    """The developers found: their view as JSON (``--json``) or as Polish text."""

    def __init__(self, *, as_json: bool) -> None:
        self._as_json = as_json

    def present(self, result: SearchDevelopersResult) -> None:
        show(DeveloperSearchView.from_result(result), self._as_json, self._text)

    @staticmethod
    def _text(result: DeveloperSearchView) -> str:
        if result.total is None:
            head = f"Deweloperzy: pokazano {result.returned}, może być więcej."
        elif result.truncated:
            head = f"Deweloperzy: {number_text(result.total)} · pokazano {result.returned}."
        else:
            head = f"Deweloperzy: {number_text(result.total)}."
        lines = [head]
        for item in result.items:
            line = f"{item.name} [{item.developer_slug}]"
            if item.offer_count is not None:
                line += f" · ofert: {number_text(item.offer_count)}"
            lines.append(line)
            if item.developer_url:
                lines.append(f"    {item.developer_url}")
        if result.hint:
            lines.append(f"Wskazówka: {result.hint}")
        if result.items:
            lines.append("W nawiasach [] slug dewelopera dla: deweloperuch developers get SLUG")
        return "\n".join(lines)
