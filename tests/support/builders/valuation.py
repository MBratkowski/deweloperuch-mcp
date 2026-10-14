"""Test data of the valuation. Payloads are derived from real rows of
docs/discovery/samples/ (copies of the sample's rows with new ids, never values made
up); the domain objects, page addresses and expected texts here are the ones several
test modules share.
"""

import copy
from typing import Any

from deweloperuch_mcp.api.dto.dto import Dto
from deweloperuch_mcp.api.dto.standalone_valuation_dto import (
    StandaloneValuationDto,
)
from deweloperuch_mcp.models.valuation import (
    ComparableTransaction,
    Valuation,
    ValuationSubject,
)
from support.providers.routes.valuation import VALUATION_PATH
from support.providers.samples import body
from support.providers.service import BASE


def valuation_with_comparables(count: int) -> Any:
    """The sample with ``count`` transactions: copies of its own, each 10 m further away
    than the one before (the service gives them nearest first [W])."""
    valuation = body("api.standalone_val")
    transactions = valuation["transactions"]
    valuation["transactions"] = []
    for index in range(count):
        item = copy.deepcopy(transactions[index % len(transactions)])
        item["distance"] = 50 + 10 * index
        item["saleRcnId"] = 700_000 + index
        valuation["transactions"].append(item)
    return valuation


SUBJECT = ValuationSubject.parse(52.2297, 21.0122, 50, "Marszałkowska 100, Warszawa")
"""What the sample api.standalone_val was asked for (its _request)."""


def api_sample() -> Any:
    return body("api.standalone_val")


def parsed(data: Any) -> StandaloneValuationDto:
    return Dto.validated(StandaloneValuationDto, data, "/api/standalone-valuation")


def mapped(data: Any, subject: ValuationSubject = SUBJECT) -> Valuation:
    return parsed(data).to_model(subject)


def comparable(distance: float | None, address: str) -> ComparableTransaction:
    return ComparableTransaction(address=address, distance_m=distance)


WITHOUT_ADDRESS = BASE + VALUATION_PATH + "?area=50&lat=52.2297&lng=21.0122"
