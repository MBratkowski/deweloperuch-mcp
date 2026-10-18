"""``GetBuildingCliPresenter``: ``buildings get`` for people or as JSON."""

from deweloperuch_mcp.consumers.cli.support.common import show
from deweloperuch_mcp.consumers.cli.support.formatting import (
    amount_text,
    count_text,
    number_text,
    per_m2_unit,
)
from deweloperuch_mcp.consumers.shared.building_views import (
    BuildingView,
    NeighbourhoodTrendView,
    TransactionView,
    UnitView,
)
from deweloperuch_mcp.models.building import WHOLE_UNIT
from deweloperuch_mcp.usecases.get_building import GetBuildingResult

_MARKETS = dict(primary="rynek pierwotny", secondary="rynek wtórny")
# [W] the meanings of the classes are read from the service's Polish labels
# (api.dto.building_dto).
_CLASSES = dict(
    regular="zwykła",
    share="udział",
    bulk="hurtowa",
    government="rządowa",
    enforcement="egzekucja",
    discount="z bonifikatą",
    anomaly_low="anomalia (nisko)",
    anomaly_high="anomalia (wysoko)",
)
_PARTIES = dict(natural_person="osoba fizyczna", legal_person="osoba prawna")
_PLN = "PLN"


class GetBuildingCliPresenter:
    """The building: its view as JSON (``--json``) or as Polish text."""

    def __init__(self, *, as_json: bool) -> None:
        self._as_json = as_json

    def present(self, result: GetBuildingResult) -> None:
        show(BuildingView.from_result(result), self._as_json, self._text)

    @classmethod
    def _text(cls, building: BuildingView) -> str:
        lines = cls._summary_lines(building)
        others = cls._other_transactions_line(building)
        if others is not None:
            lines.append(others)
        for unit in building.units:
            lines.append(cls._unit_line(unit))
            lines += [cls._transaction_line(transaction) for transaction in unit.transactions]
        lines += cls._trend_or_hint(building)
        return "\n".join(lines)

    @staticmethod
    def _summary_lines(building: BuildingView) -> list[str]:
        """The building's address (its town when the register gives none), page, place,
        the service's averages and the counts of its units and transactions."""
        lines = [f"{building.name or building.city} [{building.building_slug}]"]
        if building.building_url:
            lines.append(f"Strona budynku: {building.building_url}")
        place = f"Miejsce: {building.city} [{building.city_slug}]"
        if building.street and building.street != building.name:
            place += f", {building.street}"
        if building.lat is not None and building.lng is not None:
            place += f" · {building.lat:.5f}, {building.lng:.5f}"
        averages = [
            amount_text(building.avg_price, _PLN),
            amount_text(building.avg_area_m2, "m²", 2),
            amount_text(building.avg_price_per_m2, per_m2_unit(_PLN), 2),
        ]
        counts = (
            f"Lokale: {number_text(building.units_total)} · transakcje: "
            f"{number_text(building.transactions_total)}"
        )
        first, last = building.first_transaction_date, building.last_transaction_date
        if first is not None and last is not None:
            counts += f" (od {first.isoformat()} do {last.isoformat()})"
        counts += f" · pokazano {len(building.units)}"
        if building.units_omitted:
            counts += f" · pominięto {building.units_omitted} (zwiększ --limit)"
        return lines + [place, "Średnio (wg serwisu): " + " · ".join(averages), counts + "."]

    @staticmethod
    def _other_transactions_line(building: BuildingView) -> str | None:
        """The transactions of the building that are no regular sale, by class; ``None``
        when there are none."""
        if not building.non_regular_transactions:
            return None
        others = " · ".join(
            f"{_CLASSES.get(word, word)} {number_text(found)}"
            for word, found in building.non_regular_transactions.items()
        )
        return f"Transakcje inne niż zwykłe: {others}."

    @classmethod
    def _trend_or_hint(cls, building: BuildingView) -> list[str]:
        """The trend around the building when it has quarters, then the hint, if any."""
        trend = building.neighbourhood_trend
        lines = cls._trend_lines(trend) if trend is not None and trend.quarters_total else []
        if building.hint:
            lines.append(f"Wskazówka: {building.hint}")
        return lines

    @staticmethod
    def _unit_line(unit: UnitView) -> str:
        parts = []
        if unit.floor is not None:
            parts.append(f"piętro {unit.floor}")
        if unit.rooms is not None:
            parts.append(f"{unit.rooms} pok.")
        parts += [amount_text(unit.area_m2, "m²", 2), unit.name]
        return " · ".join(parts)

    @staticmethod
    def _transaction_line(transaction: TransactionView) -> str:
        unit = transaction.currency or ""
        day = transaction.date.isoformat() if transaction.date else "?"
        parts = [
            amount_text(transaction.price, unit, 2),
            amount_text(transaction.price_per_m2, per_m2_unit(unit), 2),
            *(
                words.get(value, value)
                for value, words in (
                    (transaction.market, _MARKETS),
                    (transaction.classification, _CLASSES),
                )
                if value is not None
            ),
        ]
        for role, party in (("kupujący", transaction.buyer), ("sprzedający", transaction.seller)):
            if party is not None:
                parts.append(f"{role}: {_PARTIES.get(party, party)}")
        if transaction.share is not None and transaction.share != WHOLE_UNIT:
            parts.append(f"udział {transaction.share}")
        return f"  {day:<10}  " + " · ".join(parts)

    @staticmethod
    def _trend_lines(trend: NeighbourhoodTrendView) -> list[str]:
        radius = "?" if trend.radius_km is None else number_text(trend.radius_km, 2)
        head = f"Trend w okolicy (promień {radius} km): średnia cena za m² i liczba transakcji"
        if trend.quarters_omitted:
            head += f" · pominięto {trend.quarters_omitted} starszych kwartałów"
        lines = [head + "."]
        for quarter in trend.quarters:
            price = amount_text(quarter.avg_price_per_m2, per_m2_unit(_PLN))
            lines.append(
                f"  {quarter.period}  {price} · transakcji: {count_text(quarter.transactions)}"
            )
        return lines
