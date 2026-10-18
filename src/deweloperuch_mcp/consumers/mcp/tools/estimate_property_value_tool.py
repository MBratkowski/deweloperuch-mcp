"""``EstimatePropertyValueTool``: the value of a flat from the RCN transactions nearby,
with at most ``MAX_COMPARABLES`` comparable transactions per call."""

from typing import Annotated

from mcp.types import CallToolResult
from pydantic import Field

from deweloperuch_mcp.consumers.mcp.presenters.estimate_property_value_mcp_presenter import (
    EstimatePropertyValueMcpPresenter,
    ValuationResult,
)
from deweloperuch_mcp.consumers.mcp.support.calls import SessionContext, run, session_of
from deweloperuch_mcp.consumers.mcp.support.inputs import DecimalNumber, OptionalChoice, whole_or
from deweloperuch_mcp.consumers.mcp.support.tool_base import ToolBase
from deweloperuch_mcp.models.valuation import (
    ADDRESS_MAX,
    POLAND_LAT,
    POLAND_LNG,
    VALUED_AREA_MAX,
    VALUED_AREA_MIN,
)
from deweloperuch_mcp.usecases.estimate_property_value import EstimatePropertyValueRequest

MAX_COMPARABLES = 50
"""Comparable transactions one result may hold: about 10.6k characters (about 210 per
transaction with the sample's addresses)."""
DEFAULT_COMPARABLES = 10

Latitude = Annotated[float, Field(ge=POLAND_LAT[0], le=POLAND_LAT[1])]
Longitude = Annotated[float, Field(ge=POLAND_LNG[0], le=POLAND_LNG[1])]
ValuedArea = Annotated[float, Field(ge=VALUED_AREA_MIN, le=VALUED_AREA_MAX)]
Address = Annotated[str, Field(max_length=ADDRESS_MAX)]
Comparables = Annotated[int, Field(ge=0, le=MAX_COMPARABLES)]


class EstimatePropertyValueTool(ToolBase):
    # [P] docs/discovery/endpoints.md, "5. Valuation": a comparative valuation from RCN
    # transactions within a radius; one request per call. T8 (docs/open-questions.md) is a
    # gap: no confirmed geocoding of an address, so the coordinates come from the user or
    # from search_locations (lat, lng of districts and streets [P]: a point of the street,
    # not of a building). [W] low_confidence: the rule of models.valuation (fewer than 5
    # transactions, this package's threshold); the widest radius only adds a statement to
    # the hint (the meaning of the service's ceiling of the radius is [W]).
    name = "estimate_property_value"
    title = "Wycena mieszkania"
    description = """\
Szacuje wartość mieszkania o danym metrażu w punkcie (lat, lng) w Polsce na podstawie \
cen transakcyjnych z Rejestru Cen Nieruchomości (RCN) z okolicy. Wynik jest \
przybliżony: to porównanie z transakcjami w pobliżu, a nie operat szacunkowy. Użyj, gdy \
użytkownik pyta, ile może być warte mieszkanie albo czy jego cena jest rynkowa.

Zwraca estimated_value (PLN), price_per_m2, radius_m i period_months (skąd i z ilu \
miesięcy są transakcje), stats (liczba, mediana, średnia, min i max ceny za m²) oraz \
comparables: najbliższe transakcje porównawcze (adres, data, cena, metraż, cena za m², \
piętro, odległość, rynek), z comparables_total, comparables_omitted, truncated i hint. \
estimated_value=null znaczy, że serwis nie podał wyceny: przeczytaj hint. \
low_confidence=true (mniej niż 5 transakcji porównawczych): wycenę podaj tylko jako \
orientacyjną, z zastrzeżeniem z hint.

Wymaga współrzędnych: narzędzie nie zamienia adresu na lat i lng. Weź je od \
użytkownika, z search_locations (ulica lub dzielnica: to punkt przybliżony, nie \
konkretny budynek) albo z get_investment (współrzędne inwestycji oferty). Każde \
wywołanie to zapytanie do serwisu: nie wyceniaj seriami wielu punktów."""

    async def __call__(
        self,
        lat: Annotated[
            Latitude,
            DecimalNumber,
            Field(
                title="Szerokość geograficzna",
                description=(
                    "Szerokość geograficzna punktu w Polsce w stopniach, np. 52.2297: pole lat "
                    "z search_locations (ulica albo dzielnica, nie samo miasto) albo ze "
                    "współrzędnych inwestycji w get_investment (dokładniejsze dla konkretnej "
                    "oferty)."
                ),
            ),
        ],
        lng: Annotated[
            Longitude,
            DecimalNumber,
            Field(
                title="Długość geograficzna",
                description=(
                    "Długość geograficzna punktu w Polsce w stopniach, np. 21.0122: pole lng "
                    "z search_locations (ulica albo dzielnica, nie samo miasto) albo ze "
                    "współrzędnych inwestycji w get_investment (dokładniejsze dla konkretnej "
                    "oferty)."
                ),
            ),
        ],
        area_m2: Annotated[
            ValuedArea,
            DecimalNumber,
            Field(title="Metraż", description="Metraż mieszkania w m², 10–500, np. 48.5."),
        ],
        ctx: SessionContext,
        address: Annotated[
            Address | None,
            OptionalChoice,
            Field(
                title="Adres",
                description=(
                    "Opcjonalny opis adresu, np. Marszałkowska 100, Warszawa. Trafia do serwisu, "
                    "ale nie wyznacza położenia: decydują lat i lng."
                ),
            ),
        ] = None,
        limit: Annotated[
            Comparables,
            whole_or(DEFAULT_COMPARABLES),
            Field(
                title="Liczba transakcji",
                description=(
                    "Ile najbliższych transakcji porównawczych zwrócić, 0–50, domyślnie 10. "
                    "Transakcja to ok. 210 znaków wyniku (50 to ok. 10,6 tys.); 0 = tylko wycena "
                    "i statystyki."
                ),
            ),
        ] = DEFAULT_COMPARABLES,
    ) -> Annotated[CallToolResult, ValuationResult]:
        session = session_of(ctx)

        def estimate() -> ValuationResult:
            request = EstimatePropertyValueRequest.parse(
                lat=lat, lng=lng, area_m2=area_m2, address=address, limit=limit
            )
            presenter = EstimatePropertyValueMcpPresenter(max_comparables=MAX_COMPARABLES)
            return presenter.present(session.estimate_property_value.execute(request))

        return await run(estimate)
