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


CISNA_SUBJECT = ValuationSubject.parse(49.2167, 22.3333, 50)
"""What the Cisna capture was asked for (tests/fixtures/api/README.md)."""


IN_CISNA: dict[str, Any] = dict(lat=49.2167, lng=22.3333, area_m2=50)
"""The same as arguments of ``estimate_property_value``."""


CISNA_OPTIONS = ("--lat", "49.2167", "--lng", "22.3333", "--area", "50")
"""The same as options of ``deweloperuch valuation estimate``."""


CISNA_CAVEAT = (
    "Wycena oparta tylko na 2 transakcjach z promienia 1 000 m (największego, jaki serwis "
    "bierze pod uwagę) z ostatnich 24 miesięcy: to orientacyjna wartość o niskiej "
    "wiarygodności. Podaj ją z tym zastrzeżeniem i z rozpiętością cen za m² tych transakcji "
    "(2 302–5 778 PLN/m²); porównaj też z cenami transakcyjnymi miasta "
    "(get_transaction_statistics)."
)
"""The caveat of the Cisna capture's estimate: few transactions (low confidence), from the
widest radius."""


AT_THE_WIDEST_RADIUS = (
    "Transakcje porównawcze pochodzą z promienia 1 000 m (największego, jaki serwis bierze "
    "pod uwagę), więc wycena opisuje szerszą okolicę i jest orientacyjna."
)
"""What an estimate from 5 or more transactions at the widest radius (1000 m) says: no
word of low confidence."""


def at_the_widest_radius(count: int) -> Any:
    """The sample with ``count`` transactions (``valuation_with_comparables``), counted so by
    its statistics, from a radius of 1 km: its own ceiling (1000 m). Edited by hand: a test
    of the rule, the service was seen at its ceiling only in Cisna."""
    valuation = valuation_with_comparables(count)
    valuation["radiusKm"] = 1
    valuation["stats"]["count"] = count
    return valuation


def api_sample() -> Any:
    return body("api.standalone_val")


def parsed(data: Any) -> StandaloneValuationDto:
    return Dto.validated(StandaloneValuationDto, data, "/api/standalone-valuation")


def mapped(data: Any, subject: ValuationSubject = SUBJECT) -> Valuation:
    return parsed(data).to_model(subject)


def comparable(distance: float | None, address: str) -> ComparableTransaction:
    return ComparableTransaction(address=address, distance_m=distance)


WITHOUT_ADDRESS = BASE + VALUATION_PATH + "?area=50&lat=52.2297&lng=21.0122"


CISNA_REQUEST = BASE + VALUATION_PATH + "?area=50&lat=49.2167&lng=22.3333"
"""The request of the Cisna capture, as the client sends it."""
