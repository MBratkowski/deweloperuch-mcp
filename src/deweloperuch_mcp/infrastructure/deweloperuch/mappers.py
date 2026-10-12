"""DTO -> domain (D3): numbers, dates and empty values normalized, backend names left here.

Pure functions, no I/O. The DTOs guarantee that numeric and date texts parse
(``infrastructure.deweloperuch.dto``), so these conversions do not fail on service data.
The backend's ``invest`` is an investment and its ``sale`` an offer; its enum values
(``PRICE_INCREASE``, ``OFFER_EVENT``...) become the domain's words, unknown ones pass
through lowercased.
"""

import datetime as dt
from collections.abc import Sequence
from dataclasses import replace

from deweloperuch_mcp.domain.investments import Investment
from deweloperuch_mcp.domain.locations import Location
from deweloperuch_mcp.domain.offers import (
    DECREASE,
    EVENT_ARCHIVED,
    EVENT_OFFER,
    EVENT_RESTORED,
    INCREASE,
    NO_CHANGE,
    Developer,
    InvestmentRef,
    ListedOffer,
    Offer,
    OfferSearchPage,
    PriceChange,
    PriceEvent,
    PriceHistory,
)
from deweloperuch_mcp.infrastructure.deweloperuch.dto import (
    CityMappingDto,
    DeveloperDto,
    InvestmentDto,
    InvestmentSaleDto,
    LocationSuggestionDto,
    OffersPageDto,
    SaleEventDto,
    SaleListItemDto,
)

_CHANGE_KINDS = {"PRICE_INCREASE": INCREASE, "PRICE_DECREASE": DECREASE, "NO_CHANGE": NO_CHANGE}
_EVENT_KINDS = {
    "OFFER_EVENT": EVENT_OFFER,
    "ARCHIVED_EVENT": EVENT_ARCHIVED,
    "RESTORED_EVENT": EVENT_RESTORED,
}


# --- values ----------------------------------------------------------------------------


def number(value: int | float | str | None) -> float | None:
    """``994012``, ``"994012"``, ``" -0.6 "`` -> float; ``""`` and ``None`` -> ``None``."""
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
    return float(value)


def day(value: str | None) -> dt.date | None:
    """``"2026-10-03"`` or an ISO datetime -> date (of the moment in UTC); ``""`` -> ``None``.

    The service sends event dates as UTC midnight (``2025-02-25T00:00:00.000Z``) [P].
    """
    text_value = (value or "").strip()
    if not text_value:
        return None
    if len(text_value) == 10:
        return dt.date.fromisoformat(text_value)
    moment = dt.datetime.fromisoformat(text_value)
    if moment.tzinfo is not None:
        moment = moment.astimezone(dt.UTC)
    return moment.date()


def text(value: str | None) -> str | None:
    """Stripped text; ``""`` and whitespace -> ``None`` (the backend sends ``""`` for none)."""
    stripped = (value or "").strip()
    return stripped or None


def change_kind(value: str | None) -> str | None:
    """``PRICE_INCREASE`` -> ``increase``, ``PRICE_DECREASE`` -> ``decrease``, ``NO_CHANGE``."""
    raw = text(value)
    return None if raw is None else _CHANGE_KINDS.get(raw, raw.lower())


def event_kind(value: str) -> str:
    """``OFFER_EVENT`` -> ``offer``, ``ARCHIVED_EVENT`` -> ``archived``, ``RESTORED_EVENT``."""
    return _EVENT_KINDS.get(value, value.lower().removesuffix("_event"))


# --- locations ---------------------------------------------------------------------------


def location_from_city(mapping: CityMappingDto) -> Location:
    return Location.city_of(
        name=mapping.city, city_slug=mapping.city_slug, offer_count=mapping.offerCount
    )


def location_from_suggestion(suggestion: LocationSuggestionDto) -> Location:
    return Location.place(
        kind=suggestion.kind,
        city=suggestion.city,
        city_slug=suggestion.citySlug,
        district=text(suggestion.district),
        street=text(suggestion.street),
        lat=number(suggestion.lat),
        lng=number(suggestion.lng),
        # [W] docs/discovery/endpoints.md, location-search: `count` is the number of offers
        # (or transactions with variant=transactions, never sent) in the area.
        offer_count=suggestion.count,
    )


# --- offers --------------------------------------------------------------------------------


def developer(dto: DeveloperDto) -> Developer:
    return Developer(
        developer_slug=dto.slug,
        name=dto.name,
        website=text(dto.website),
        description=text(dto.description),
    )


def price_events(events: Sequence[SaleEventDto]) -> tuple[PriceEvent, ...]:
    """Chronological; events of one day in the order the service recorded them (by id).

    The service does not sort them (sample ``api.inv_sale_events``). Events without a
    date (none seen so far) come first.
    """
    ordered = sorted(events, key=lambda e: (day(e.event_date) or dt.date.min, e.sale_event_id))
    return tuple(
        PriceEvent(date=day(e.event_date), kind=event_kind(e.event_type), price=number(e.amount))
        for e in ordered
    )


def _history(sale: InvestmentSaleDto | SaleListItemDto) -> PriceHistory:
    return PriceHistory(
        since_start=PriceChange(
            pln=number(sale.start_amount_difference),
            percent=number(sale.start_amount_difference_percent),
        ),
        created_on=day(sale.creation_date),
        last_event_on=day(sale.last_event_date),
        last_changed_on=day(sale.last_change_event_date),
    )


def offer(sale: InvestmentSaleDto | SaleListItemDto, history: PriceHistory | None = None) -> Offer:
    return Offer(
        offer_id=sale.sale_id,
        name=sale.name,
        status=sale.status,
        price=number(sale.amount),
        currency=text(sale.currency),
        area_m2=number(sale.size),
        history=_history(sale) if history is None else history,
    )


def listed_offer(item: SaleListItemDto) -> ListedOffer:
    """An offer of the search results: its last change and its number of events too."""
    history = replace(
        _history(item),
        last_change=PriceChange(
            pln=number(item.last_amount_difference),
            percent=number(item.last_amount_difference_percent),
            direction=change_kind(item.last_event_type),
        ),
        events_count=item.total_events,
    )
    return ListedOffer(
        offer=offer(item, history),
        investment=InvestmentRef(
            investment_slug=item.invest.slug,
            name=item.invest.name,
            city=text(item.invest.city),
            city_slug=text(item.invest.city_slug),
            developer=Developer(
                developer_slug=item.invest.developer.slug, name=item.invest.developer.name
            ),
        ),
    )


def offer_search_page(page: OffersPageDto) -> OfferSearchPage:
    """The page as the service paged it (its own ``page`` and ``perPage``)."""
    return OfferSearchPage(
        items=tuple(listed_offer(item) for item in page.data),
        total=page.pagination.total,
        page=page.pagination.page,
        per_page=page.pagination.perPage,
    )


# --- investments -------------------------------------------------------------------------


def investment(dto: InvestmentDto) -> Investment:
    """The investment with every offer, in the service's order."""
    return Investment(
        investment_id=dto.invest_id,
        investment_slug=dto.slug,
        name=dto.name,
        status=dto.status,
        city=dto.city,
        city_slug=dto.city_slug,
        street=text(dto.street),
        lat=number(dto.latitude),
        lng=number(dto.longitude),
        currency=text(dto.currency),
        developer=developer(dto.developer),
        avg_price=number(dto.avg_amount),
        avg_area_m2=number(dto.avg_size),
        avg_price_per_m2=number(dto.avg_price_sqm),
        offers_active=dto.active_offers,
        offers_total=dto.total_offers,
        offers=tuple(offer(sale) for sale in dto.sale),
    )
