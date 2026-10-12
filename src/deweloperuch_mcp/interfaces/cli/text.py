"""The text ``deweloperuch`` prints for people (Polish): one formatter per result, and the
Polish way of writing numbers (digit groups, decimal comma)."""

import math

from deweloperuch_mcp.bootstrap import StopRecord, StopState, UnreadableStop, format_time
from deweloperuch_mcp.domain.values import BROWSABLE_PAGES
from deweloperuch_mcp.interfaces.text import printable
from deweloperuch_mcp.interfaces.views import (
    GovernmentStatistics,
    Investment,
    Location,
    LocationSearchResult,
    OfferBase,
    OfferDetail,
    OfferSearchResult,
    PriceEvent,
)

_KINDS = {"city": "miasto", "district": "dzielnica", "street": "ulica"}
_STATUSES = {"active": "aktywna", "archived": "archiwalna"}
_EVENTS = {"offer": "cena", "archived": "wycofanie", "restored": "przywrócenie"}


def format_locations(result: LocationSearchResult) -> str:
    if result.total is None:
        head = f"Lokalizacje: pokazano {result.returned}, może być więcej."
    else:
        head = f"Lokalizacje: {result.total}."
    lines = [head, *(_location_line(item) for item in result.items)]
    if result.hint:
        lines.append(f"Wskazówka: {result.hint}")
    if result.items:
        lines.append("W nawiasach [] slug miasta dla: deweloperuch offers search CITY_SLUG")
    return "\n".join(lines)


def _location_line(item: Location) -> str:
    name = item.name if item.name == item.city else f"{item.name}, {item.city}"
    line = f"{_KINDS.get(item.kind, item.kind):<9}  {name} [{item.city_slug}]"
    if item.offer_count is not None:
        # [W] docs/discovery/endpoints.md, location-search: `count` of districts and streets
        # is the number of offers; hence "ok." for them.
        about = "" if item.kind == "city" else "ok. "
        line += f" · ofert: {about}{_number(item.offer_count)}"
    return line


def format_offer_search(result: OfferSearchResult) -> str:
    head = [f"Pasujące oferty: {_number(result.total)}"]
    if result.pages_available:
        head.append(f"strona {result.page} z {result.pages_available} (po {result.per_page})")
    head.append(f"pokazano {result.returned}")
    if result.truncated:
        head.append(f"obcięte: serwis pozwala przejrzeć najwyżej {BROWSABLE_PAGES} stron")
    lines = [" · ".join(head) + "."]
    if result.hint:
        lines.append(f"Wskazówka: {result.hint}")
    if result.list_url:
        lines.append(f"Ta lista na deweloperuch.pl: {result.list_url}")
    for item in result.items:
        lines.append(_offer_line(item))
        where = f"    {item.investment_name} [{item.investment_slug}] · {item.developer_name}"
        lines.append(where + (f" · {item.city}" if item.city else ""))
        if item.investment_url:
            lines.append(f"    {item.investment_url}")
    if result.items:
        lines.append(
            "Szczegóły oferty: deweloperuch offers get OFFER_ID --investment INVESTMENT_SLUG"
        )
    return "\n".join(lines)


def format_offer(offer: OfferDetail) -> str:
    unit = offer.currency or ""
    lines = [
        f"[{offer.offer_id}] {offer.name} · {_status(offer.status)}",
        "Cena: " + " · ".join(_measures(offer)),
    ]
    if offer.price_change_since_start is not None:
        lines.append(f"Od pierwszej ceny: {_change(offer)}")
    lines.append(f"Inwestycja: {offer.investment_name} [{offer.investment_slug}] · {offer.city}")
    if offer.investment_url:
        lines.append(f"Strona inwestycji: {offer.investment_url}")
    lines.append(f"Deweloper: {offer.developer.name} [{offer.developer.developer_slug}]")
    if offer.developer_url:
        lines.append(f"Profil dewelopera: {offer.developer_url}")
    dates = [
        f"{label} {value.isoformat()}"
        for label, value in (
            ("dodana", offer.creation_date),
            ("ostatnie zdarzenie", offer.last_event_date),
            ("ostatnia zmiana", offer.last_change_date),
        )
        if value is not None
    ]
    if dates:
        lines.append("Daty: " + " · ".join(dates))
    lines.append(f"Historia ceny ({len(offer.price_history)}):")
    lines += [_event_line(event, unit) for event in offer.price_history]
    return "\n".join(lines)


def format_investment(investment: Investment) -> str:
    unit = investment.currency or ""
    place = f"Miejsce: {investment.city} [{investment.city_slug}]"
    if investment.street:
        place += f", {investment.street}"
    if investment.lat is not None and investment.lng is not None:
        place += f" · {investment.lat:.5f}, {investment.lng:.5f}"
    averages = [
        _amount(investment.avg_price, unit),
        _amount(investment.avg_area_m2, "m²", 2),
        _amount(investment.avg_price_per_m2, _per_m2(unit), 2),
    ]
    count = (
        f"Oferty: aktywne {_count(investment.offers_active)} z {_count(investment.offers_total)}"
        f" · pokazano {len(investment.offers)}"
    )
    if investment.offers_omitted:
        count += f" · pominięto {investment.offers_omitted} (zwiększ --limit)"
    lines = [f"{investment.name} [{investment.investment_slug}] · {_status(investment.status)}"]
    if investment.investment_url:
        lines.append(f"Strona inwestycji: {investment.investment_url}")
    lines += [
        place,
        f"Deweloper: {investment.developer.name} [{investment.developer.developer_slug}]",
    ]
    if investment.developer_url:
        lines.append(f"Profil dewelopera: {investment.developer_url}")
    lines += ["Średnio (aktywne oferty): " + " · ".join(averages), count + "."]
    for offer in investment.offers:
        lines.append(_offer_line(offer))
        if offer.price_history is not None:
            lines += [_event_line(event, unit) for event in offer.price_history]
    return "\n".join(lines)


def format_government_statistics(result: GovernmentStatistics) -> str:
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
    header = ["Okres", *(f"[{index}]" for index in range(1, len(result.series) + 1))]
    rows = [
        [period, *(_cell(series.points[index].value) for series in result.series)]
        for index, period in enumerate(result.periods)
    ]
    widths = [max(len(row[column]) for row in [header, *rows]) for column in range(len(header))]
    for row in [header, *rows]:
        cells = [row[0].ljust(widths[0])]
        cells += [cell.rjust(width) for cell, width in zip(row[1:], widths[1:], strict=True)]
        lines.append("  ".join(cells))
    return "\n".join(lines)


def format_stop_status(state: StopState) -> str:
    stop = state.stop
    if stop is None:
        lines = ["Brak STOP: zapytania do deweloperuch.pl nie są wstrzymane."]
    elif isinstance(stop, UnreadableStop):
        lines = [
            "STOP aktywny bezterminowo: zapis jest nieczytelny.",
            f"Problem: {printable(stop.problem)}",
        ]
    elif state.active:
        lines = [f"STOP aktywny: {stop.label}.", _stop_origin(stop)]
        if stop.until is None:
            lines.append("Wygasa: nie, trwa do zdjęcia.")
        else:
            left = max(1, math.ceil(state.seconds_left or 0))
            lines.append(f"Wygasa: {format_time(stop.until)} (za {left} s).")
    else:
        until = "" if stop.until is None else f" {format_time(stop.until)}"
        lines = [
            f"STOP wygasł{until}: {stop.label}.",
            _stop_origin(stop),
            "Zapytania do deweloperuch.pl nie są wstrzymane.",
        ]
    if state.active:
        lines.append(
            "Blokadę zdejmuje użytkownik po sprawdzeniu przyczyny: deweloperuch stop clear"
        )
    lines.append(f"Plik: {printable(str(state.path))}")
    return "\n".join(lines)


def format_stop_clear(before: StopState) -> str:
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


def _stop_origin(stop: StopRecord) -> str:
    pid = "" if stop.pid is None else f" (PID {stop.pid})"
    return f"Od: {format_time(stop.since)} · źródło: {stop.source}{pid}"


def _offer_line(offer: OfferBase) -> str:
    parts = [f"[{offer.offer_id}] {offer.name}", *_measures(offer), _status(offer.status)]
    if offer.price_change_since_start:  # neither unknown nor zero
        parts.append(f"od pierwszej ceny {_change(offer)}")
    return " · ".join(parts)


def _measures(offer: OfferBase) -> list[str]:
    unit = offer.currency or ""
    return [
        _amount(offer.price, unit),
        _amount(offer.area_m2, "m²", 2),
        _amount(offer.price_per_m2, _per_m2(unit), 2),
    ]


def _per_m2(currency: str) -> str:
    """``PLN/m²``; without a currency no unit at all (not ``/m²``)."""
    return f"{currency}/m²" if currency else ""


def _change(offer: OfferBase) -> str:
    text = _amount(offer.price_change_since_start, offer.currency or "", signed=True)
    pct = offer.price_change_since_start_pct
    return text if pct is None else f"{text} ({_number(pct, 2, signed=True)}%)"


def _event_line(event: PriceEvent, unit: str) -> str:
    day = event.date.isoformat() if event.date else "?"
    return f"  {day:<10}  {_EVENTS.get(event.kind, event.kind):<12}  {_amount(event.price, unit)}"


def _cell(value: float | None) -> str:
    """A value of a statistics table: up to 2 decimals; ``–`` for a period without data."""
    return "–" if value is None else _number(value, 2)


def _status(status: str) -> str:
    return _STATUSES.get(status, status)


def _count(value: int | None) -> str:
    return "?" if value is None else _number(value)


def _amount(value: float | None, unit: str, decimals: int = 0, *, signed: bool = False) -> str:
    number = "?" if value is None else _number(value, decimals, signed=signed)
    return f"{number} {unit}".rstrip()


def _number(value: float, decimals: int = 0, *, signed: bool = False) -> str:
    """``1234567.5`` -> ``1 234 567,5``: Polish digit groups and decimal comma, no trailing
    zeros; ``signed`` adds ``+`` to positive numbers. Zero is ``0``, never ``-0``/``+0``."""
    text = f"{value:{'+' if signed else ''},.{decimals}f}"
    if decimals:
        text = text.rstrip("0").rstrip(".")
    if text.lstrip("+-") == "0":  # -0.001 rounds to "-0"
        return "0"
    return text.replace(",", " ").replace(".", ",")
