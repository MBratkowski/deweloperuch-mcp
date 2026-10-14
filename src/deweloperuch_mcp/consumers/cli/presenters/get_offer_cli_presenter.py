"""``GetOfferCliPresenter`` (D17 reference): ``offers get`` for people or as JSON."""

from deweloperuch_mcp.consumers.cli.presenters.offer_cli_presenter import OfferCliPresenter
from deweloperuch_mcp.consumers.cli.support.common import show
from deweloperuch_mcp.consumers.cli.support.formatting import amount_text, number_text, status_text
from deweloperuch_mcp.consumers.shared.offer_views import OfferDetailView, PriceFlagsView
from deweloperuch_mcp.usecases.get_offer import GetOfferResult


class GetOfferCliPresenter(OfferCliPresenter):
    """The offer: its view as JSON (``--json``) or as Polish text."""

    def __init__(self, *, as_json: bool) -> None:
        self._as_json = as_json

    def present(self, result: GetOfferResult) -> None:
        show(OfferDetailView.from_result(result), self._as_json, self._text)

    @classmethod
    def _text(cls, offer: OfferDetailView) -> str:
        unit = offer.currency or ""
        lines = [
            f"[{offer.offer_id}] {offer.name} · {status_text(offer.status)}",
            "Cena: " + " · ".join(cls.measures(offer)),
        ]
        if offer.price_change_since_start is not None:
            lines.append(f"Od pierwszej ceny: {cls.change(offer)}")
        lines.append(
            f"Inwestycja: {offer.investment_name} [{offer.investment_slug}] · {offer.city}"
        )
        if offer.investment_url:
            lines.append(f"Strona inwestycji: {offer.investment_url}")
        lines.append(f"Deweloper: {offer.developer.name} [{offer.developer.developer_slug}]")
        if offer.developer_url:
            lines.append(f"Profil dewelopera: {offer.developer_url}")
        dates = [
            f"{label} {value.isoformat()}"
            for label, value in (
                ("dodana", offer.creation_date),
                ("ostatnie zdarzenie", offer.last_event_date),
                ("ostatnia zmiana", offer.last_change_date),
            )
            if value is not None
        ]
        if dates:
            lines.append("Daty: " + " · ".join(dates))
        if offer.price_flags is not None:
            lines += cls._flag_lines(offer.price_flags, unit)
        lines.append(f"Historia ceny ({len(offer.price_history)}):")
        lines += [cls.event_line(event, unit) for event in offer.price_history]
        return "\n".join(lines)

    @staticmethod
    def _flag_lines(flags: PriceFlagsView, unit: str) -> list[str]:
        def pct(value: float | None) -> str:
            return "brak" if value is None else f"{number_text(value, 2)}%"

        suspicious = (
            "tak (ostatnia obniżka do 30 dni po podwyżce, a cena nie niższa niż najniższa z 30 "
            "dni przed obniżką)"
            if flags.suspicious_reduction
            else "nie"
        )
        return [
            f"Najniższa cena: z 30 dni {amount_text(flags.lowest_price_30d, unit)} · z 90 dni "
            f"{amount_text(flags.lowest_price_90d, unit)}",
            f"Zmiany ceny: {flags.price_changes} · największa obniżka "
            f"{pct(flags.largest_drop_pct)} · największa podwyżka {pct(flags.largest_rise_pct)}",
            f"Podejrzana obniżka: {suspicious}",
        ]
