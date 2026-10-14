"""Test data of an investment and its offers. Payloads are derived from real rows of
docs/discovery/samples/ (copies of the sample's rows with new ids, never values made
up); the domain objects, page addresses and expected texts here are the ones several
test modules share.
"""

import copy
from typing import Any

from deweloperuch_mcp.api.dto import (
    investment_dto,
)
from deweloperuch_mcp.models.investment import Investment
from deweloperuch_mcp.models.offer import Offer
from support.providers.samples import body
from support.providers.service import PAGES


def investment_with_offers(count: int) -> Any:
    """The ``smolna`` sample with ``count`` offers (copies of its offers with new ids)."""
    investment = body("api.map_inv_visible")
    offers = investment["sale"]
    investment["sale"] = []
    for index in range(count):
        offer = copy.deepcopy(offers[index % len(offers)])
        offer["sale_id"] = 800_000 + index
        investment["sale"].append(offer)
    return investment


SMOLNA_PAGE = PAGES + "/sopot/deweloperzy/invest-komfort-spolka-akcyjna/smolna"


DEVELOPER_PAGE = PAGES + "/sopot/deweloperzy/invest-komfort-spolka-akcyjna"


def sale(**changes: Any) -> dict[str, Any]:
    item: dict[str, Any] = body("api.map_inv_visible")["sale"][0]
    item.update(changes)
    return item


def smolna(**changes: Any) -> Investment:
    data = body("api.map_inv_visible")
    data.update(changes)
    return investment_dto.InvestmentDto.model_validate(data).to_model()


def offer(offer_id: int, status: str = "active", price: float | None = 1.0) -> Offer:
    return Offer(offer_id=offer_id, name=f"M{offer_id}", status=status, price=price, area_m2=50.0)
