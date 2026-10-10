"""DTO -> domain mapping (D3): numbers, dates and empty values normalized, domain names.

Pure functions, no I/O. The DTOs guarantee that numeric and date texts parse
(``deweloperuch_mcp.client.dto``), so these conversions do not fail on service data.
"""

import datetime as dt
import math
from collections.abc import Mapping, Sequence

from deweloperuch_mcp.client.dto import (
    CityMappingDto,
    DeveloperDto,
    InvestmentDto,
    InvestmentSaleDto,
    LocationSuggestionDto,
    OffersPageDto,
    SaleEventDto,
    SaleListItemDto,
)
from deweloperuch_mcp.domain.models import (
    Developer,
    Investment,
    Location,
    Offer,
    OfferDetail,
    OfferSearchResult,
    OfferSummary,
    PriceEvent,
)

# Backend values -> domain values; unknown values pass through lowercased.
_CHANGE_KINDS = {
    "PRICE_INCREASE": "increase",
    "PRICE_DECREASE": "decrease",
    "NO_CHANGE": "no_change",
}
_EVENT_KINDS = {"OFFER_EVENT": "offer", "ARCHIVED_EVENT": "archived", "RESTORED_EVENT": "restored"}


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


def price_per_m2(price: float | None, area: float | None) -> float | None:
    if price is None or not area:
        return None
    return round(price / area, 2)


# --- locations ---------------------------------------------------------------------------


def location_from_city(mapping: CityMappingDto) -> Location:
    return Location(
        kind="city",
        name=mapping.city,
        city=mapping.city,
        city_slug=mapping.city_slug,
        offer_count=mapping.offerCount,
    )


def location_from_suggestion(suggestion: LocationSuggestionDto) -> Location:
    district = text(suggestion.district)
    street = text(suggestion.street)
    if suggestion.kind == "street":
        name = street
    elif suggestion.kind == "district":
        name = district
    else:  # other kinds are [H]: the most specific name there is
        name = street or district
    return Location(
        kind=suggestion.kind,
        name=name or suggestion.city,
        city=suggestion.city,
        city_slug=suggestion.citySlug,
        district=district,
        street=street,
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


def price_history(events: Sequence[SaleEventDto]) -> list[PriceEvent]:
    """Chronological; events of one day in the order the service recorded them (by id).

    The service does not sort them (sample ``api.inv_sale_events``). Events without a
    date (none seen so far) come first.
    """
    ordered = sorted(events, key=lambda e: (day(e.event_date) or dt.date.min, e.sale_event_id))
    return [
        PriceEvent(date=day(e.event_date), kind=event_kind(e.event_type), price=number(e.amount))
        for e in ordered
    ]


def _offer_fields(sale: InvestmentSaleDto | SaleListItemDto) -> dict[str, object]:
    price = number(sale.amount)
    area = number(sale.size)
    return {
        "offer_id": sale.sale_id,
        "name": sale.name,
        "status": sale.status,
        "price": price,
        "currency": text(sale.currency),
        "area_m2": area,
        "price_per_m2": price_per_m2(price, area),
        "price_change_since_start": number(sale.start_amount_difference),
        "price_change_since_start_pct": number(sale.start_amount_difference_percent),
        "creation_date": day(sale.creation_date),
        "last_event_date": day(sale.last_event_date),
        "last_change_date": day(sale.last_change_event_date),
    }


def offer(sale: InvestmentSaleDto, history: Sequence[SaleEventDto] | None = None) -> Offer:
    return Offer.model_validate(
        {
            **_offer_fields(sale),
            "price_history": None if history is None else price_history(history),
        }
    )


def offer_summary(item: SaleListItemDto) -> OfferSummary:
    return OfferSummary.model_validate(
        {
            **_offer_fields(item),
            "last_price_change": number(item.last_amount_difference),
            "last_price_change_pct": number(item.last_amount_difference_percent),
            "last_price_change_kind": change_kind(item.last_event_type),
            "events_count": item.total_events,
            "investment_slug": item.invest.slug,
            "investment_name": item.invest.name,
            "city": text(item.invest.city),
            "city_slug": text(item.invest.city_slug),
            "developer_slug": item.invest.developer.slug,
            "developer_name": item.invest.developer.name,
        }
    )


def offer_detail(
    investment: InvestmentDto, sale: InvestmentSaleDto, events: Sequence[SaleEventDto]
) -> OfferDetail:
    return OfferDetail.model_validate(
        {
            **_offer_fields(sale),
            "investment_slug": investment.slug,
            "investment_name": investment.name,
            "city": investment.city,
            "city_slug": investment.city_slug,
            "developer": developer(investment.developer),
            "price_history": price_history(events),
        }
    )


def offer_search_result(page: OffersPageDto, *, max_pages: int) -> OfferSearchResult:
    """D4: the page plus what can be browsed at all (``max_pages`` x ``per_page``)."""
    pagination = page.pagination
    total, per_page = pagination.total, pagination.perPage
    pages_available = min(max_pages, math.ceil(total / per_page)) if per_page > 0 else 0
    truncated = total > max_pages * per_page
    items = [offer_summary(item) for item in page.data]
    hint = None
    if truncated:
        hint = (
            f"Pasujących ofert jest {total}, a serwis pozwala przejrzeć najwyżej {max_pages} "
            f"stron po {per_page} ({max_pages * per_page}). Zawęź filtry (cena, metraż)"
            + (" albo zwiększ per_page do 100." if per_page < 100 else ".")
        )
    elif total == 0:
        hint = (
            "Brak ofert spełniających kryteria. Sprawdź slug miasta (search_locations) "
            "i poluzuj filtry."
        )
    elif not items:
        hint = f"Strona {pagination.page} jest pusta; dostępne strony: 1–{pages_available}."
    return OfferSearchResult(
        total=total,
        returned=len(items),
        truncated=truncated,
        page=pagination.page,
        per_page=per_page,
        pages_available=pages_available,
        hint=hint,
        items=items,
    )


# --- investments -------------------------------------------------------------------------


def investment(
    dto: InvestmentDto,
    *,
    limit: int | None = None,
    history: Mapping[int, Sequence[SaleEventDto]] | None = None,
) -> Investment:
    """The investment with its offers: active first, at most ``limit``.

    With ``history`` (offer id -> events) every returned offer gets its price history
    (empty when the map has no entry for it); without it ``price_history`` is ``None``.
    """
    ordered = sorted(dto.sale, key=lambda sale: sale.status != "active")  # stable
    kept = ordered if limit is None else ordered[:limit]
    offers = [
        offer(sale, None if history is None else history.get(sale.sale_id, ())) for sale in kept
    ]
    return Investment(
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
        offers=offers,
        offers_omitted=len(ordered) - len(kept),
    )
