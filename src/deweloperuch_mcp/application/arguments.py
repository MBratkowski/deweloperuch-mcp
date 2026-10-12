"""The parameters of the operations, as the CLI and the MCP server take them (D13).

The application's contract shared by both interfaces: the names of the parameters
(``city``, ``price_min``, ``per_page``...), the order they are checked in, and how a
refused value is explained with them, pointing to the operation that gives the right
value (``search_locations``, ``search_offers``). The domain refuses values in its own
words (``InvalidValueError``: which value, which rule, what was given); the functions
here turn raw arguments into domain values and word every refusal for the caller as an
``InvalidInputError``. Nothing is sent before they return.
"""

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import NamedTuple

from deweloperuch_mcp.domain.errors import (
    InvalidInputError,
    InvalidValueError,
    LowNotAboveHigh,
    OneOf,
    SlugText,
    TextLength,
    TrueOrFalse,
    ValueName,
    WholeNumber,
)
from deweloperuch_mcp.domain.offers import OfferSearchCriteria
from deweloperuch_mcp.domain.statistics import DEFAULT_PERIODS, Dataset, PeriodCount
from deweloperuch_mcp.domain.values import (
    DEFAULT_PAGE_SIZE,
    AreaRange,
    CitySlug,
    InvestmentSlug,
    LocationQuery,
    LocationSlug,
    OfferId,
    OffersLimit,
    OfferSort,
    PageNumber,
    PageSize,
    PriceRange,
    flag,
)

PARAMETERS: Mapping[ValueName, str] = {
    ValueName.QUERY: "query",
    ValueName.CITY: "city",
    ValueName.INVESTMENT: "investment_slug",
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
    ValueName.PAGE: "page",
    ValueName.PAGE_SIZE: "per_page",
    ValueName.SORT: "sort",
    ValueName.OFFERS_LIMIT: "limit",
    ValueName.HISTORY: "include_history",
    ValueName.DATASET: "dataset",
    ValueName.PERIODS: "periods",
}
"""The parameter that carries each value (a range by the prefix of its two ends)."""

_SLUGS: Mapping[ValueName, str] = {
    ValueName.CITY: "slug miasta (np. warszawa) albo polska; slug podaje search_locations",
    ValueName.INVESTMENT: (
        "slug inwestycji, np. smolna; podaje go search_offers (investment_slug)"
    ),
    ValueName.STATISTICS_LOCATION: (
        "polska, agregat (7-miast, 10-miast, 6-miast-bez-warszawy) albo slug miasta bez "
        "polskich znaków, np. warszawa, krakow, jastrzebie (Jastrzębie-Zdrój)"
    ),
}
"""What a slug parameter takes and where it comes from."""

_NOTES: Mapping[ValueName, str] = {
    ValueName.OFFER: " (identyfikator oferty z search_offers)",
    ValueName.OFFERS_LIMIT: " (liczba ofert w wyniku)",
    ValueName.PERIODS: " (liczba ostatnich okresów)",
}
"""What a whole number counts, when its unit does not say it."""


def explained(err: InvalidValueError) -> str:
    """The refusal of ``err`` with the parameter's name and what to give instead."""
    name, given = PARAMETERS[err.value], err.given
    match err.rule:
        case WholeNumber(low, high, unit):
            if err.value is ValueName.PAGE:
                note = f" (serwis ma najwyżej {high} stron)"
            elif unit is not None:
                note = f" ({unit})"
            else:
                note = _NOTES.get(err.value, "")
            return (
                f"{name} musi być liczbą całkowitą z zakresu {low}–{high}{note}, podano {given!r}."
            )
        case OneOf(choices):
            listed = ", ".join(map(str, choices))
            if err.value is ValueName.PAGE_SIZE:
                return (
                    f"{name} musi być jedną z wartości {listed} (inne serwis zamienia na 10), "
                    f"podano {given!r}."
                )
            if err.value is ValueName.SORT:
                return (
                    f"{name} musi być jedną z wartości {listed} albo pusty (domyślna kolejność "
                    f"serwisu), podano {given!r}."
                )
            return f"{name} musi być jedną z wartości {listed}, podano {given!r}."
        case SlugText():
            return f"{name}: oczekiwano {_SLUGS[err.value]}; podano {given!r}."
        case TextLength(low, high):
            return (
                f"{name}: podaj od {low} do {high} znaków nazwy miasta, dzielnicy lub ulicy, "
                f"podano {given!r}."
            )
        case TrueOrFalse():
            return f"{name} musi być true albo false, podano {given!r}."
        case LowNotAboveHigh(low, high):
            return f"{name}_min ({low}) jest większe niż {name}_max ({high}); zamień je miejscami."


@contextmanager
def _parameters() -> Iterator[None]:
    try:
        yield
    except InvalidValueError as err:
        raise InvalidInputError(explained(err)) from err


# --- the operations' arguments, checked in the order of their parameters -------------------------


def location_query(query: object) -> LocationQuery:
    with _parameters():
        return LocationQuery.parse(query)


def offer_search(
    city: object,
    *,
    price_min: object = None,
    price_max: object = None,
    area_min: object = None,
    area_max: object = None,
    sort: object = None,
    page: object = 1,
    per_page: object = DEFAULT_PAGE_SIZE,
) -> OfferSearchCriteria:
    """Checked in this order: city, price, area, sort, page, page size."""
    with _parameters():
        return OfferSearchCriteria(
            city=CitySlug.parse(city),
            price=PriceRange.parse(price_min, price_max),
            area=AreaRange.parse(area_min, area_max),
            sort=OfferSort.parse(sort),
            page=PageNumber.parse(page),
            per_page=PageSize.parse(per_page),
        )


class OfferArguments(NamedTuple):
    offer_id: OfferId
    investment: InvestmentSlug


def offer(offer_id: object, investment_slug: object) -> OfferArguments:
    with _parameters():
        return OfferArguments(OfferId.parse(offer_id), InvestmentSlug.parse(investment_slug))


class InvestmentArguments(NamedTuple):
    investment: InvestmentSlug
    include_history: bool
    limit: OffersLimit | None


def investment(
    investment_slug: object, *, include_history: object = False, limit: object = None
) -> InvestmentArguments:
    with _parameters():
        return InvestmentArguments(
            InvestmentSlug.parse(investment_slug),
            flag(ValueName.HISTORY, include_history),
            OffersLimit.parse(limit),
        )


class StatisticsArguments(NamedTuple):
    location: LocationSlug
    dataset: Dataset
    periods: PeriodCount


def government_statistics(
    location: object, dataset: object, *, periods: object = DEFAULT_PERIODS
) -> StatisticsArguments:
    with _parameters():
        return StatisticsArguments(
            LocationSlug.parse(location), Dataset.parse(dataset), PeriodCount.parse(periods)
        )
