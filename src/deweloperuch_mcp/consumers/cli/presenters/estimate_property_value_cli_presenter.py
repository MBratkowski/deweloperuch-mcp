"""``EstimatePropertyValueCliPresenter``: ``valuation estimate`` for people or as JSON."""

from deweloperuch_mcp.consumers.cli.support.common import show
from deweloperuch_mcp.consumers.cli.support.formatting import amount_text, number_text
from deweloperuch_mcp.consumers.shared.text import printable
from deweloperuch_mcp.consumers.shared.valuation_views import (
    ComparableTransactionView,
    PricePerM2StatsView,
    ValuationView,
)
from deweloperuch_mcp.usecases.estimate_property_value import EstimatePropertyValueResult

_MARKETS = {"primary": "rynek pierwotny", "secondary": "rynek wtórny"}


class EstimatePropertyValueCliPresenter:
    """The valuation: its view as JSON (``--json``) or as Polish text."""

    def __init__(self, *, as_json: bool) -> None:
        self._as_json = as_json

    def present(self, result: EstimatePropertyValueResult) -> None:
        show(
            ValuationView.from_result(result),
            self._as_json,
            lambda view: self._text(view, result.valuation_hint),
        )

    @classmethod
    def _text(cls, result: ValuationView, valuation_hint: str | None) -> str:
        """The estimate, where it comes from and the statistics, then one line per
        comparable transaction, the nearest first."""
        area = amount_text(result.area_m2, "m²", 2)
        lines = [f"Wycena mieszkania {area} · {result.lat:.5f}, {result.lng:.5f}"]
        if result.address:
            lines.append(f"Adres (opis): {printable(result.address)}")
        if result.estimated_value is None:
            lines.append("Szacowana wartość: brak.")
        else:
            value = amount_text(result.estimated_value, "PLN")
            per_m2 = amount_text(result.price_per_m2, "PLN/m²")
            lines.append(f"Szacowana wartość: {value} · {per_m2}")
            source = ["Na podstawie transakcji z Rejestru Cen Nieruchomości (RCN)"]
            if result.radius_m is not None:
                source.append(f"w promieniu {number_text(result.radius_m)} m")
            if result.period_months is not None:
                source.append(f"z ostatnich {result.period_months} miesięcy")
            lines.append(" ".join(source) + "; to przybliżenie, nie operat szacunkowy.")
        if result.stats is not None:
            lines.append(cls._price_stats_line(result.stats))
        # Comparable transactions left out are said on the line of their count.
        if valuation_hint:
            lines.append(f"Wskazówka: {valuation_hint}")
        count = (
            f"Transakcje porównawcze: {result.comparables_total} · pokazano "
            f"{len(result.comparables)}"
        )
        if result.comparables_omitted:
            count += f" · pominięto {result.comparables_omitted} (zwiększ --limit)"
        lines.append(count + ".")
        lines += [cls._comparable_line(item) for item in result.comparables]
        return "\n".join(lines)

    @staticmethod
    def _price_stats_line(stats: PricePerM2StatsView) -> str:
        values = (
            ("mediana", stats.median_price_per_m2),
            ("średnia", stats.average_price_per_m2),
            ("min", stats.min_price_per_m2),
            ("max", stats.max_price_per_m2),
        )
        parts = [f"{label} {number_text(value)}" for label, value in values if value is not None]
        count = "" if stats.count is None else f" (liczba: {number_text(stats.count)})"
        shown = " · ".join(parts) + " PLN/m²" if parts else "brak"
        return f"Statystyki cen za m² podane przez serwis{count}: {shown}"

    @staticmethod
    def _comparable_line(item: ComparableTransactionView) -> str:
        day = item.date.isoformat() if item.date else "?"
        distance = "?" if item.distance_m is None else f"ok. {number_text(item.distance_m)} m"
        parts = [
            printable(item.address or "?"),
            amount_text(item.area_m2, "m²", 2),
            amount_text(item.price, "PLN"),
            amount_text(item.price_per_m2, "PLN/m²"),
        ]
        if item.floor is not None:
            parts.append(f"piętro {item.floor}")
        if item.market:
            parts.append(_MARKETS.get(item.market, item.market))
        line = f"  {day:<10}  {distance:>10}  " + " · ".join(parts)
        if item.building_slug:
            line += f" [{item.building_slug}]"
        return line
