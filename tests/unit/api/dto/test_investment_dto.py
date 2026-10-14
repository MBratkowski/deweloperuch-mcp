"""Tests of ``deweloperuch_mcp.api.dto.investment_dto``."""

import datetime as dt

from deweloperuch_mcp.api.dto import investment_dto
from deweloperuch_mcp.models.offer import DeveloperRef
from deweloperuch_mcp.models.price_history import PriceChange
from support.providers.samples import body
from support.providers.service import LINKS, PAGES

SMOLNA = PAGES + "/sopot/deweloperzy/invest-komfort-spolka-akcyjna/smolna"


DEVELOPER = PAGES + "/sopot/deweloperzy/invest-komfort-spolka-akcyjna"


def investment_sample(**changes: object) -> investment_dto.InvestmentDto:
    data = body("api.map_inv_visible")
    data.update(changes)
    return investment_dto.InvestmentDto.model_validate(data)


def test_offer_of_an_investment() -> None:
    sale = next(s for s in investment_sample().sale if s.sale_id == 2377)

    offer = sale.to_model()

    assert (offer.offer_id, offer.name, offer.price, offer.area_m2) == (
        2377,
        "C224",
        1620175.0,
        69.5,
    )
    assert offer.history.since_start == PriceChange(pln=175.0, percent=0.01)
    assert offer.history.last_change == PriceChange()  # not given for investments
    assert offer.history.created_on == dt.date(2025, 2, 25)


def test_investment_values_are_normalized() -> None:
    investment = investment_sample().to_model()

    assert (investment.investment_id, investment.investment_slug) == (33, "smolna")
    assert (investment.name, investment.status) == ("Smolna", "active")
    assert (investment.city, investment.city_slug, investment.street) == (
        "Sopot",
        "sopot",
        "Świemirowo",
    )
    assert (investment.lat, investment.lng) == (54.42735985, 18.55839032)
    assert investment.developer == DeveloperRef(
        developer_slug="invest-komfort-spolka-akcyjna", name="Invest Komfort Spółka Akcyjna Sp.K."
    )
    assert (investment.offers_active, investment.offers_total) == (3, 16)
    assert [offer.offer_id for offer in investment.offers] == [206087, 2377, 2386]
    assert all(offer.history.events is None for offer in investment.offers)
    assert (LINKS.investment(investment.ref), LINKS.developer(investment.ref)) == (
        SMOLNA,
        DEVELOPER,
    )


def test_investment_without_a_developer_slug_has_no_links() -> None:
    sample = body("api.map_inv_visible")
    sample["developer"]["slug"] = ""

    investment = investment_dto.InvestmentDto.model_validate(sample).to_model()

    assert (LINKS.investment(investment.ref), LINKS.developer(investment.ref)) == (None, None)


def test_empty_street_and_missing_coordinates_become_none() -> None:
    investment = investment_sample(street="", latitude="", longitude=None).to_model()

    assert (investment.street, investment.lat, investment.lng) == (None, None, None)
