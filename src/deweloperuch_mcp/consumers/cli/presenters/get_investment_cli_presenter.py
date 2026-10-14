"""``GetInvestmentCliPresenter``: ``investments get`` for people or as JSON."""

from deweloperuch_mcp.consumers.cli.presenters.offer_cli_presenter import OfferCliPresenter
from deweloperuch_mcp.consumers.cli.support.common import show
from deweloperuch_mcp.consumers.cli.support.formatting import (
    amount_text,
    count_text,
    per_m2_unit,
    status_text,
)
from deweloperuch_mcp.consumers.shared.investment_views import InvestmentView
from deweloperuch_mcp.usecases.get_investment import GetInvestmentResult


class GetInvestmentCliPresenter(OfferCliPresenter):
    """The investment and its offers: its view as JSON (``--json``) or as Polish text."""

    def __init__(self, *, as_json: bool) -> None:
        self._as_json = as_json

    def present(self, result: GetInvestmentResult) -> None:
        show(InvestmentView.from_result(result), self._as_json, self._text)

    @classmethod
    def _text(cls, investment: InvestmentView) -> str:
        unit = investment.currency or ""
        place = f"Miejsce: {investment.city} [{investment.city_slug}]"
        if investment.street:
            place += f", {investment.street}"
        if investment.lat is not None and investment.lng is not None:
            place += f" · {investment.lat:.5f}, {investment.lng:.5f}"
        averages = [
            amount_text(investment.avg_price, unit),
            amount_text(investment.avg_area_m2, "m²", 2),
            amount_text(investment.avg_price_per_m2, per_m2_unit(unit), 2),
        ]
        count = (
            f"Oferty: aktywne {count_text(investment.offers_active)} z "
            f"{count_text(investment.offers_total)} · pokazano {len(investment.offers)}"
        )
        if investment.offers_omitted:
            count += f" · pominięto {investment.offers_omitted} (zwiększ --limit)"
        lines = [
            f"{investment.name} [{investment.investment_slug}] · {status_text(investment.status)}"
        ]
        if investment.investment_url:
            lines.append(f"Strona inwestycji: {investment.investment_url}")
        lines += [
            place,
            f"Deweloper: {investment.developer.name} [{investment.developer.developer_slug}]",
        ]
        if investment.developer_url:
            lines.append(f"Profil dewelopera: {investment.developer_url}")
        lines += ["Średnio (aktywne oferty): " + " · ".join(averages), count + "."]
        for offer in investment.offers:
            lines.append(cls.offer_line(offer))
            if offer.price_history is not None:
                lines += [cls.event_line(event, unit) for event in offer.price_history]
        return "\n".join(lines)
