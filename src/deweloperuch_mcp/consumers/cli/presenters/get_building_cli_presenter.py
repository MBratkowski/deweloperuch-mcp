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
        lines = [f"{building.name} [{building.building_slug}]"]
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
        count = (
            f"Lokale: {number_text(building.units_total)} · transakcje: "
            f"{number_text(building.transactions_total)}"
        )
        first, last = building.first_transaction_date, building.last_transaction_date
        if first is not None and last is not None:
            count += f" (od {first.isoformat()} do {last.isoformat()})"
        count += f" · pokazano {len(building.units)}"
        if building.units_omitted:
            count += f" · pominięto {building.units_omitted} (zwiększ --limit)"
        lines += [place, "Średnio (wg serwisu): " + " · ".join(averages), count + "."]
        for unit in building.units:
            lines.append(cls._unit_line(unit))
            lines += [cls._transaction_line(transaction) for transaction in unit.transactions]
        if building.neighbourhood_trend is not None:
            lines += cls._trend_lines(building.neighbourhood_trend)
        return "\n".join(lines)

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
