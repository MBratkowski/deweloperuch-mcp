"""``GetBuildingMcpPresenter``: ``get_building``'s result for a model, and its output schema
(``BuildingResult``).

Cut down from the view (``consumers.shared.building_views``): no numbers or register
designations of the units, the currency only when it is not PLN, the share only when it
is not the whole unit, the street only when it is not the building's name, the counts of
the transactions that are no regular sale only when there are some; the units the use
case kept, with ``units_returned``, ``units_omitted`` and ``truncated`` (D4), and the
quarters of the trend it kept, with how many there are.
"""

import datetime as dt

from pydantic import Field

from deweloperuch_mcp.consumers.mcp.support.mcp_model import McpModel
from deweloperuch_mcp.consumers.shared.building_views import (
    BuildingView,
    NeighbourhoodTrendView,
    TransactionView,
    UnitView,
)
from deweloperuch_mcp.models.building import WHOLE_UNIT
from deweloperuch_mcp.usecases.get_building import GetBuildingResult

PLN = "PLN"

UNITS_ORDER = "Lokale od tego z najnowszą transakcją."
TRANSACTIONS_ORDER = "Transakcje lokalu od najstarszej."
TRANSACTION_PRICE = (
    "Cena transakcyjna (za tyle lokal sprzedano, nie ofertowa) w walucie currency (domyślnie PLN)."
)
PRICE_PER_M2 = "Cena transakcyjna za m² w walucie currency (domyślnie PLN)."
# [W] api.dto.building_dto: that `avg_*` are means follows from the names.
SERVICE_AVERAGE = "podana przez serwis"
MARKET = "primary (rynek pierwotny) albo secondary (rynek wtórny)."
# [W] docs/discovery/entities.md: the classes are [P], their meanings come from the
# service's Polish labels (api.dto.building_dto).
CLASSIFICATION = (
    "Rodzaj transakcji wg serwisu: regular (zwykła), share (udział), bulk (hurtowa), "
    "government (rządowa), enforcement (egzekucja), discount (z bonifikatą), anomaly_low "
    "albo anomaly_high (cena odstająca w dół albo w górę)."
)
NON_REGULAR = (
    "Transakcje z classification innym niż regular w całym budynku: liczba wg rodzaju "
    "(słowa jak w "
    'classification), np. {"share": 1}; brak pola: brak takich transakcji. To nie zwykła '
    "sprzedaż całego lokalu po cenie rynkowej: nie uśredniaj ich ze zwykłymi. "
    # [W] api.dto.building_dto: so in the one building checked (open question T48).
    "Średnie avg_* serwisu prawdopodobnie ich nie obejmują (sprawdzone w jednym budynku)."
)
PARTY = "natural_person (osoba fizyczna) albo legal_person (osoba prawna, np. firma)."
BUILDING_URL = (
    "Strona budynku z cenami transakcyjnymi na deweloperuch.pl: podaj ją użytkownikowi jako link."
)

# Class docstrings would become schema descriptions for the model: comments instead.


class TransactionItem(McpModel):
    date: dt.date | None = None
    price: float | None = Field(None, description=TRANSACTION_PRICE)
    price_per_m2: float | None = Field(None, description=PRICE_PER_M2)
    currency: str | None = Field(None, description="Waluta; brak pola = PLN.")
    market: str | None = Field(None, description=MARKET)
    classification: str | None = Field(None, description=CLASSIFICATION)
    buyer: str | None = Field(None, description=PARTY)
    seller: str | None = Field(None, description=PARTY)
    share: str | None = Field(
        None, description="Sprzedany udział w lokalu (np. 1/2), tylko gdy nie cały lokal."
    )


class UnitItem(McpModel):
    # A unit (a flat) of the building; get_building has no other view of it.
    floor: int | None = Field(None, description="Piętro wg rejestru cen.")
    rooms: int | None = Field(None, description="Liczba pokoi wg rejestru cen.")
    area_m2: float | None = Field(None, description="Powierzchnia lokalu w m².")
    transactions: list[TransactionItem] = Field(description=TRANSACTIONS_ORDER)


class TrendQuarterItem(McpModel):
    period: str = Field(description="Kwartał, np. 2025-Q3.")
    avg_price_per_m2: float | None = Field(None, description="Średnia cena za m² w PLN.")
    transactions: int | None = Field(None, description="Liczba transakcji w kwartale.")


class NeighbourhoodTrendResult(McpModel):
    radius_km: float | None = Field(None, description="Promień okolicy budynku w km.")
    total: int = Field(description="Wszystkie kwartały, które ma serwis (0: brak trendu).")
    returned: int = Field(description="Kwartały w wyniku: najnowsze z nich.")
    truncated: bool = Field(description="true: są starsze kwartały niż pokazane.")
    quarters: list[TrendQuarterItem] = Field(description="Kwartały od najstarszego.")


class BuildingResult(McpModel):
    building_slug: str = Field(description="Identyfikator do ponownego get_building.")
    name: str | None = Field(
        None,
        description=(
            "Adres budynku wg rejestru cen; brak pola: rejestr nie podaje adresu (miejscowość "
            "w city)."
        ),
    )
    building_url: str | None = Field(None, description=BUILDING_URL)
    city: str = Field(description="Miasto budynku.")
    city_slug: str = Field(description="city_slug jak w search_locations.")
    street: str | None = Field(None, description="Ulica, tylko gdy inna niż name.")
    lat: float | None = Field(None, description="Współrzędne budynku (WGS84).")
    lng: float | None = Field(None, description="Współrzędne budynku (WGS84).")
    avg_price: float | None = Field(
        None, description=f"Średnia cena transakcyjna lokalu w PLN, {SERVICE_AVERAGE}."
    )
    avg_area_m2: float | None = Field(
        None, description=f"Średnia powierzchnia lokalu w m², {SERVICE_AVERAGE}."
    )
    avg_price_per_m2: float | None = Field(
        None, description=f"Średnia cena za m² w PLN, {SERVICE_AVERAGE}."
    )
    first_transaction_date: dt.date | None = Field(
        None, description="Data najstarszej transakcji w budynku."
    )
    last_transaction_date: dt.date | None = Field(
        None, description="Data najnowszej transakcji w budynku."
    )
    units_total: int = Field(description="Wszystkie lokale budynku w rejestrze cen.")
    transactions_total: int = Field(description="Wszystkie transakcje lokali budynku.")
    non_regular_transactions: dict[str, int] | None = Field(None, description=NON_REGULAR)
    units: list[UnitItem] = Field(description=UNITS_ORDER)
    units_returned: int = Field(description="Lokali na liście units.")
    units_omitted: int = Field(description="Lokali pominiętych przez limit.")
    truncated: bool = Field(description="true: lista units jest niepełna (units_omitted > 0).")
    hint: str | None = Field(
        None,
        description=(
            "Co zrobić dalej albo czego brakuje w wyniku, np. brak trendu w okolicy budynku."
        ),
    )
    neighbourhood_trend: NeighbourhoodTrendResult | None = Field(
        None,
        description=(
            "Średnia cena za m² transakcji w okolicy budynku w kolejnych kwartałach; tylko "
            "przy include_trend=true."
        ),
    )


class GetBuildingMcpPresenter:
    """The building as its view has it (``BuildingView``), cut down for a model."""

    def present(self, result: GetBuildingResult) -> BuildingResult:
        view = BuildingView.from_result(result)
        trend = view.neighbourhood_trend
        return BuildingResult(
            building_slug=view.building_slug,
            name=view.name,
            building_url=view.building_url,
            city=view.city,
            city_slug=view.city_slug,
            street=None if view.street == view.name else view.street,
            lat=view.lat,
            lng=view.lng,
            avg_price=view.avg_price,
            avg_area_m2=view.avg_area_m2,
            avg_price_per_m2=view.avg_price_per_m2,
            first_transaction_date=view.first_transaction_date,
            last_transaction_date=view.last_transaction_date,
            units_total=view.units_total,
            transactions_total=view.transactions_total,
            non_regular_transactions=view.non_regular_transactions or None,
            units=[self._unit(unit) for unit in view.units],
            units_returned=len(view.units),
            units_omitted=view.units_omitted,
            truncated=view.units_omitted > 0,
            hint=view.hint,
            neighbourhood_trend=None if trend is None else self._trend(trend),
        )

    @classmethod
    def _unit(cls, unit: UnitView) -> UnitItem:
        return UnitItem(
            floor=unit.floor,
            rooms=unit.rooms,
            area_m2=unit.area_m2,
            transactions=[cls._transaction(t) for t in unit.transactions],
        )

    @staticmethod
    def _transaction(transaction: TransactionView) -> TransactionItem:
        share = transaction.share
        return TransactionItem(
            date=transaction.date,
            price=transaction.price,
            price_per_m2=transaction.price_per_m2,
            currency=None if transaction.currency == PLN else transaction.currency,
            market=transaction.market,
            classification=transaction.classification,
            buyer=transaction.buyer,
            seller=transaction.seller,
            share=None if share == WHOLE_UNIT else share,
        )

    @staticmethod
    def _trend(trend: NeighbourhoodTrendView) -> NeighbourhoodTrendResult:
        return NeighbourhoodTrendResult(
            radius_km=trend.radius_km,
            total=trend.quarters_total,
            returned=len(trend.quarters),
            truncated=trend.quarters_omitted > 0,
            quarters=[
                TrendQuarterItem(
                    period=quarter.period,
                    avg_price_per_m2=quarter.avg_price_per_m2,
                    transactions=quarter.transactions,
                )
                for quarter in trend.quarters
            ],
        )
