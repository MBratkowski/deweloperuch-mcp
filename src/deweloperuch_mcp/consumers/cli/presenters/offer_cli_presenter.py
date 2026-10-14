"""``OfferCliPresenter``: the base of the presenters that print offers (D17 reference): the
lines of one offer and of its price history, shared by ``offers search``, ``offers get``
and ``investments get``."""

from deweloperuch_mcp.consumers.cli.support.formatting import (
    amount_text,
    number_text,
    per_m2_unit,
    status_text,
)
from deweloperuch_mcp.consumers.shared.offer_views import OfferBaseView, PriceEventView

_EVENTS = {"offer": "cena", "archived": "wycofanie", "restored": "przywrócenie"}


class OfferCliPresenter:
    """The lines of an offer; subclasses print their command's result (``present``)."""

    @classmethod
    def offer_line(cls, offer: OfferBaseView) -> str:
        parts = [
            f"[{offer.offer_id}] {offer.name}",
            *cls.measures(offer),
            status_text(offer.status),
        ]
        if offer.price_change_since_start:  # neither unknown nor zero
            parts.append(f"od pierwszej ceny {cls.change(offer)}")
        return " · ".join(parts)

    @staticmethod
    def measures(offer: OfferBaseView) -> list[str]:
        unit = offer.currency or ""
        return [
            amount_text(offer.price, unit),
            amount_text(offer.area_m2, "m²", 2),
            amount_text(offer.price_per_m2, per_m2_unit(unit), 2),
        ]

    @staticmethod
    def change(offer: OfferBaseView) -> str:
        text = amount_text(offer.price_change_since_start, offer.currency or "", signed=True)
        pct = offer.price_change_since_start_pct
        return text if pct is None else f"{text} ({number_text(pct, 2, signed=True)}%)"

    @staticmethod
    def event_line(event: PriceEventView, unit: str) -> str:
        day = event.date.isoformat() if event.date else "?"
        kind = _EVENTS.get(event.kind, event.kind)
        return f"  {day:<10}  {kind:<12}  {amount_text(event.price, unit)}"
