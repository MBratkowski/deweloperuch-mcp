"""Test data of the transaction statistics. Payloads are derived from real rows of
docs/discovery/samples/ (copies of the sample's rows with new ids, never values made
up); the domain objects, page addresses and expected texts here are the ones several
test modules share.
"""

import copy
from typing import Any

from deweloperuch_mcp.models.transaction_series import (
    Granularity,
    TransactionCity,
    TransactionPeriod,
    TransactionSeries,
)
from support.providers.samples import body
from support.providers.service import BASE


def _labels(first_year: int, count: int, per_year: int, label: str) -> list[str]:
    return [
        label.format(year=first_year + index // per_year, number=index % per_year + 1)
        for index in range(count)
    ]


def months(count: int) -> Any:
    """The monthly sample with ``count`` months from 2021-01: copies of its rows."""
    data = body("api.monthly_tx")
    rows = data["data"]
    data["data"] = []
    for index, label in enumerate(_labels(2021, count, 12, "{year}-{number:02d}")):
        row = copy.deepcopy(rows[index % len(rows)])
        row["month"] = label
        data["data"].append(row)
    return data


def quarters(count: int) -> Any:
    """The quarterly sample with ``count`` quarters from 2017-Q1: copies of its rows."""
    data = body("api.avg_trend_city")
    rows = data["data"]
    data["data"] = []
    for index, label in enumerate(_labels(2017, count, 4, "{year}-Q{number}")):
        row = copy.deepcopy(rows[index % len(rows)])
        row["period"] = label
        data["data"].append(row)
    return data


WARSZAWA = TransactionCity("warszawa")


def period(label: str, transactions: int = 10, **measures: float) -> TransactionPeriod:
    return TransactionPeriod(label, transactions, **measures)


def series(*labels: str, granularity: Granularity = Granularity.MONTH) -> TransactionSeries:
    return TransactionSeries(WARSZAWA, granularity, tuple(period(label) for label in labels))


STATS_PAGE = BASE + "/statystyki/ceny-transakcyjne/mieszkania"


# [P 2026-10-13] live observation (Warsaw 2026-05/06): no transactions, every measure 0.
ZERO_MONTH = {
    "transaction_count": 0,
    "med_price_sqm": 0,
    "avg_price_sqm": 0,
    "med_size": 0,
    "avg_size": 0,
    "med_amount": 0,
    "avg_amount": 0,
}
