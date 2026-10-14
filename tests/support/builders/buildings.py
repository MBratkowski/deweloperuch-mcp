"""Test data of a building of the price register. Payloads are derived from real rows of
docs/discovery/samples/ (copies of the sample's rows with new ids, never values made
up); the domain objects, page addresses and expected texts here are the ones several
test modules share.
"""

import copy
from typing import Any

from deweloperuch_mcp import identity
from support.providers.routes.buildings import (
    UNKNOWN_BUILDING,
)
from support.providers.samples import body


def building_with_units(count: int, transactions: int = 1) -> Any:
    """The sample with ``count`` units: copies of its units with new numbers. With more
    than one transaction each, a unit gets that many copies of the sample's transactions
    (their real rows, dates and prices, cycled) with new numbers."""
    data = body("api.tx_visible")
    units = data["sale"]
    deeds = [deed for unit in units for deed in unit["sale_event_rcn"]]
    data["sale"] = []
    for index in range(count):
        unit = copy.deepcopy(units[index % len(units)])
        unit["sale_rcn_id"] = 700_000 + index
        if transactions > 1:
            unit["sale_event_rcn"] = [
                dict(copy.deepcopy(deeds[n % len(deeds)]), sale_event_rcn_id=index * 100 + n)
                for n in range(transactions)
            ]
        data["sale"].append(unit)
    return data


def trend_with_quarters(count: int) -> Any:
    """The trend sample with ``count`` quarters from 2006-Q2 on (its rows repeated)."""
    trend = body("api.avg_trend_building")
    rows = trend["data"]
    trend["data"] = []
    for index in range(count):
        year, quarter = divmod(index + 1, 4)
        period = str(2006 + year) + "-Q" + str(quarter + 1)
        trend["data"].append(dict(rows[index % len(rows)], period=period))
    return trend


UNKNOWN = identity.BASE_URL + "/api/map/transactions/visible/" + UNKNOWN_BUILDING


NOT_FOUND = (
    f"Nie znaleziono budynku '{UNKNOWN_BUILDING}'. Slug budynku to ostatni człon adresu jego "
    "strony z cenami transakcyjnymi na deweloperuch" + ".pl, np. 23-marca-79c-sopot albo "
    "aleja-krakowska-279-warszawa."
)
