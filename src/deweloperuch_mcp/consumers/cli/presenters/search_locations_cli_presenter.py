"""``SearchLocationsCliPresenter``: ``locations search`` for people or as JSON."""

from deweloperuch_mcp.consumers.cli.support.common import show
from deweloperuch_mcp.consumers.cli.support.formatting import number_text
from deweloperuch_mcp.consumers.shared.location_views import LocationSearchView, LocationView
from deweloperuch_mcp.usecases.search_locations import SearchLocationsResult

_KINDS = {"city": "miasto", "district": "dzielnica", "street": "ulica"}


class SearchLocationsCliPresenter:
    """The locations: their view as JSON (``--json``) or as Polish text."""

    def __init__(self, *, as_json: bool) -> None:
        self._as_json = as_json

    def present(self, result: SearchLocationsResult) -> None:
        show(LocationSearchView.from_result(result), self._as_json, self._text)

    @classmethod
    def _text(cls, result: LocationSearchView) -> str:
        if result.total is None:
            head = f"Lokalizacje: pokazano {result.returned}, może być więcej."
        else:
            head = f"Lokalizacje: {result.total}."
        lines = [head, *(cls._location_line(item) for item in result.items)]
        if result.hint:
            lines.append(f"Wskazówka: {result.hint}")
        if result.items:
            lines.append("W nawiasach [] slug miasta dla: deweloperuch offers search CITY_SLUG")
        return "\n".join(lines)

    @staticmethod
    def _location_line(item: LocationView) -> str:
        name = item.name if item.name == item.city else f"{item.name}, {item.city}"
        line = f"{_KINDS.get(item.kind, item.kind):<9}  {name} [{item.city_slug}]"
        if item.offer_count is not None:
            # [W] docs/discovery/endpoints.md, location-search: `count` of districts and
            # streets is the number of offers; hence "ok." for them.
            about = "" if item.kind == "city" else "ok. "
            line += f" · ofert: {about}{number_text(item.offer_count)}"
        return line
