"""The parameters of the operations, as the CLI and the MCP server take them (D13, D17).

The application's contract shared by both interfaces: the names of the parameters
(``city``, ``price_min``, ``per_page``...), the order they are checked in, and how a
refused value is explained with them, pointing to the operation that gives the right
value (``search_locations``, ``search_offers``). The models refuse values in their own
words (``InvalidValueError``: which value, which rule, what was given); each operation's
``<Op>Request.parse`` (D17) turns raw arguments into model values inside
``ParameterCheck``, which words every refusal for the caller as an ``InvalidInputError``.
Nothing is sent before ``parse`` returns.
"""

from collections.abc import Mapping
from typing import assert_never

from deweloperuch_mcp.models.errors import (
    InvalidInputError,
    InvalidValueError,
    LowNotAboveHigh,
    NumberBetween,
    OneCity,
    OneOf,
    SlugText,
    TextLength,
    TrueOrFalse,
    ValueName,
    WholeNumber,
)

PARAMETERS: Mapping[ValueName, str] = {
    ValueName.QUERY: "query",
    ValueName.CITY: "city",
    ValueName.INVESTMENT: "investment_slug",
    ValueName.DEVELOPER: "developer_slug",
    ValueName.STATISTICS_LOCATION: "location",
    ValueName.OFFER: "offer_id",
    ValueName.AMOUNT: "amount",
    ValueName.AREA: "area",
    ValueName.PRICE_FROM: "price_min",
    ValueName.PRICE_TO: "price_max",
    ValueName.PRICE_RANGE: "price",
    ValueName.AREA_FROM: "area_min",
    ValueName.AREA_TO: "area_max",
    ValueName.AREA_RANGE: "area",
    ValueName.PRICE_PER_M2: "price_per_m2",
    ValueName.PRICE_PER_M2_FROM: "price_per_m2_min",
    ValueName.PRICE_PER_M2_TO: "price_per_m2_max",
    ValueName.PRICE_PER_M2_RANGE: "price_per_m2",
    ValueName.DISTRICT: "district",
    ValueName.PRICE_DROPPED: "price_dropped",
    ValueName.OFFER_STATUS: "status",
    ValueName.PAGE: "page",
    ValueName.PAGE_SIZE: "per_page",
    ValueName.SORT: "sort",
    ValueName.OFFERS_LIMIT: "limit",
    ValueName.INVESTMENTS_LIMIT: "limit",
    ValueName.TOP_DEVELOPERS: "top_developers",
    ValueName.HISTORY: "include_history",
    ValueName.DATASET: "dataset",
    ValueName.PERIODS: "periods",
    ValueName.DEVELOPER_NAME: "name",
    ValueName.DEVELOPER_MATCHES: "limit",
    ValueName.INVESTMENTS_CITY: "city",
    ValueName.INVESTMENT_NAME: "name",
    ValueName.INVESTMENT_SORT: "sort",
    ValueName.TRANSACTIONS_CITY: "city",
    ValueName.GRANULARITY: "granularity",
    ValueName.RANKING_LEVEL: "level",
    ValueName.RANKING_ORDER: "sort",
    ValueName.RANKING_LIMIT: "limit",
    ValueName.MIN_TRANSACTIONS: "min_transactions",
    ValueName.BUILDING: "building_slug",
    ValueName.UNITS_LIMIT: "limit",
    ValueName.TREND: "include_trend",
    ValueName.LATITUDE: "lat",
    ValueName.LONGITUDE: "lng",
    ValueName.VALUED_AREA: "area_m2",
    ValueName.ADDRESS: "address",
    ValueName.COMPARABLES_LIMIT: "limit",
}
"""The parameter that carries each value (a range by the prefix of its two ends)."""

_SLUGS: Mapping[ValueName, str] = {
    ValueName.CITY: "slug miasta (np. warszawa) albo polska; slug podaje search_locations",
    ValueName.INVESTMENT: (
        "slug inwestycji, np. smolna; podaje go search_offers (investment_slug)"
    ),
    ValueName.DEVELOPER: (
        "slug dewelopera, np. atal; podają go search_developers, search_offers i "
        "search_investments (developer_slug)"
    ),
    ValueName.STATISTICS_LOCATION: (
        "polska, agregat (7-miast, 10-miast, 6-miast-bez-warszawy) albo slug miasta bez "
        "polskich znaków, np. warszawa, krakow, jastrzebie (Jastrzębie-Zdrój)"
    ),
    ValueName.INVESTMENTS_CITY: (
        "slug jednego miasta (np. warszawa, sopot; nie polska); slug podaje search_locations"
    ),
    ValueName.TRANSACTIONS_CITY: (
        "slug miasta bez polskich znaków, np. warszawa, krakow (nie polska: cała Polska nie "
        "jest obsługiwana); slug podaje search_locations (city_slug)"
    ),
    ValueName.BUILDING: (
        "slug budynku: małe litery bez polskich znaków, cyfry i myślniki, np. 23-marca-79c-sopot"
    ),
}
"""What a slug parameter takes and where it comes from."""

_NOTES: Mapping[ValueName, str] = {
    ValueName.OFFER: " (identyfikator oferty z search_offers)",
    ValueName.OFFERS_LIMIT: " (liczba ofert w wyniku)",
    ValueName.INVESTMENTS_LIMIT: " (liczba inwestycji w wyniku)",
    ValueName.TOP_DEVELOPERS: " (liczba deweloperów w wyniku)",
    ValueName.PERIODS: " (liczba ostatnich okresów)",
    ValueName.DEVELOPER_MATCHES: " (liczba deweloperów w wyniku)",
    ValueName.RANKING_LIMIT: " (liczba pozycji rankingu)",
    ValueName.MIN_TRANSACTIONS: " (najmniejsza liczba transakcji miejsca w rankingu)",
    ValueName.UNITS_LIMIT: " (liczba lokali w wyniku)",
    ValueName.COMPARABLES_LIMIT: " (liczba transakcji porównawczych w wyniku)",
}
"""What a whole number counts, when its unit does not say it."""

_COORDINATES = (
    " (stopnie; tylko punkty w Polsce, współrzędne ulicy lub dzielnicy podaje search_locations)"
)
_NUMBER_NOTES: Mapping[ValueName, str] = {
    ValueName.LATITUDE: _COORDINATES,
    ValueName.LONGITUDE: _COORDINATES,
}
"""Where a number comes from, when its unit does not say it."""

_NAMED: Mapping[ValueName, str] = {
    ValueName.INVESTMENT_NAME: "nazwy inwestycji",
    ValueName.DEVELOPER_NAME: "nazwy dewelopera",
}
"""What a text is a part of, when it is not a place (``search_locations``)."""


class ParameterCheck:
    """``with ParameterCheck():``: a value the models refuse (``InvalidValueError``)
    becomes an ``InvalidInputError`` worded with its parameter (``explained``). The
    requests' ``parse`` (D17) check their values in it.
    """

    @classmethod
    def explained(cls, err: InvalidValueError) -> str:
        """The refusal of ``err`` with the parameter's name and what to give instead."""
        name, given = PARAMETERS[err.value], err.given
        match err.rule:
            case WholeNumber() as rule:
                said = cls._whole_number(name, err, rule)
            case OneOf() as rule:
                said = cls._one_of(name, err, rule)
            case SlugText():
                said = f"{name}: oczekiwano {_SLUGS[err.value]}; podano {given!r}."
            case NumberBetween() as rule:
                said = cls._number_between(name, err, rule)
            case TextLength() as rule:
                said = cls._text_length(name, err, rule)
            case TrueOrFalse():
                said = f"{name} musi być true albo false, podano {given!r}."
            case OneCity():
                said = cls._one_city(name, err)
            case LowNotAboveHigh(low, high):
                said = (
                    f"{name}_min ({low}) jest większe niż {name}_max ({high}); zamień je miejscami."
                )
            case _:
                assert_never(err.rule)
        return said

    @staticmethod
    def _whole_number(name: str, err: InvalidValueError, rule: WholeNumber) -> str:
        if err.value is ValueName.PAGE:
            note = f" (serwis ma najwyżej {rule.high} stron)"
        elif rule.unit is not None:
            note = f" ({rule.unit})"
        else:
            note = _NOTES.get(err.value, "")
        return (
            f"{name} musi być liczbą całkowitą z zakresu {rule.low}–{rule.high}{note}, "
            f"podano {err.given!r}."
        )

    @staticmethod
    def _one_of(name: str, err: InvalidValueError, rule: OneOf) -> str:
        listed = ", ".join(map(str, rule.choices))
        if err.value is ValueName.PAGE_SIZE:
            listed += " (inne serwis zamienia na 10)"
        elif err.value is ValueName.SORT:
            listed += " albo pusty (domyślna kolejność serwisu)"
        return f"{name} musi być jedną z wartości {listed}, podano {err.given!r}."

    @staticmethod
    def _number_between(name: str, err: InvalidValueError, rule: NumberBetween) -> str:
        note = f" {rule.unit}" if rule.unit else _NUMBER_NOTES.get(err.value, "")
        return (
            f"{name} musi być liczbą z zakresu {rule.low:g}–{rule.high:g}{note}, "
            f"podano {err.given!r}."
        )

    @staticmethod
    def _text_length(name: str, err: InvalidValueError, rule: TextLength) -> str:
        low, high, given = rule.low, rule.high, err.given
        if err.value is ValueName.ADDRESS:
            return (
                f"{name}: podaj od {low} do {high} znaków adresu albo pomiń ten parametr, "
                f"podano {given!r}."
            )
        if err.value is ValueName.DISTRICT:
            return (
                f"{name}: podaj nazwę dzielnicy (od {low} do {high} znaków) tak, jak "
                "zwraca ją search_locations (kind=district), np. Mokotów; "
                f"podano {given!r}."
            )
        named = _NAMED.get(err.value, "nazwy miasta, dzielnicy lub ulicy")
        return f"{name}: podaj od {low} do {high} znaków {named}, podano {given!r}."

    @staticmethod
    def _one_city(name: str, err: InvalidValueError) -> str:
        if err.value is ValueName.DISTRICT:
            return (
                f"{name} działa tylko z jednym miastem: podaj jako city slug miasta tej "
                "dzielnicy (search_locations zwraca go przy dzielnicy), a nie polska; "
                f"podano {err.given!r}."
            )
        return (
            f"{name}: statystyki rynku są tylko dla jednego miasta; podaj city_slug miasta "
            f"z search_locations (np. warszawa), a nie polska; podano {err.given!r}."
        )

    def __enter__(self) -> None:
        return None

    def __exit__(
        self, kind: type[BaseException] | None, err: BaseException | None, _trace: object
    ) -> None:
        if isinstance(err, InvalidValueError):
            raise InvalidInputError(self.explained(err)) from err
