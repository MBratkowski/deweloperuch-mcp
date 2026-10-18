"""Test data of the transaction statistics. Payloads are derived from real rows of
docs/discovery/samples/ (copies of the sample's rows with new ids, never values made
up) or are the whole real body of tests/fixtures/api/ (``warszawa_months``); the domain
objects, page addresses and expected texts here are the ones several test modules share.
"""

import copy
import json
from typing import Any

from deweloperuch_mcp.models.transaction_series import (
    Granularity,
    TransactionCity,
    TransactionPeriod,
    TransactionSeries,
)
from support.paths import API_FIXTURES
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


MONTHLY_WARSZAWA = API_FIXTURES / "monthly_tx_warszawa_20261015.json"
"""Every month of Warsaw (2021-01..2026-07) as the service sent them on 2026-10-15, with
the real tail of incomplete months (tests/fixtures/api/README.md)."""


QUARTERLY_WARSZAWA = API_FIXTURES / "avg_trend_city_warszawa_20261016.json"
"""Every quarter of Warsaw (2017-Q1..2026-Q3) as the service sent them on 2026-10-16."""


MONTHLY_KARPACZ = API_FIXTURES / "monthly_tx_karpacz_20261016.json"
"""Every month of Karpacz (2021-01..2025-12), a small town, as sent on 2026-10-16: a median
of 1 transaction a month, 26 months without any."""


def warszawa_months() -> Any:
    """The whole body of ``MONTHLY_WARSZAWA``, parsed."""
    return json.loads(MONTHLY_WARSZAWA.read_text(encoding="utf-8"))


def warszawa_quarters() -> Any:
    """The whole body of ``QUARTERLY_WARSZAWA``, parsed."""
    return json.loads(QUARTERLY_WARSZAWA.read_text(encoding="utf-8"))


def karpacz_months() -> Any:
    """The whole body of ``MONTHLY_KARPACZ``, parsed."""
    return json.loads(MONTHLY_KARPACZ.read_text(encoding="utf-8"))


WARSZAWA = TransactionCity("warszawa")


def period(label: str, transactions: int = 10, **measures: Any) -> TransactionPeriod:
    """``measures``: prices and areas by name (``median_price_per_m2=16000.0``...)."""
    return TransactionPeriod(label, transactions, **measures)


def series(*labels: str, granularity: Granularity = Granularity.MONTH) -> TransactionSeries:
    return TransactionSeries(WARSZAWA, granularity, tuple(period(label) for label in labels))


def counted(
    first: str, *counts: int, granularity: Granularity = Granularity.MONTH
) -> TransactionSeries:
    """Consecutive periods from ``first`` (``2025-04``, ``2025-Q1``) with these numbers of
    transactions and no measures."""
    year, number = first.split("-")
    per_year = 12 if granularity is Granularity.MONTH else 4
    label = "{year}-{number:02d}" if granularity is Granularity.MONTH else "{year}-Q{number}"
    start = int(year) * per_year + int(number.lstrip("Q")) - 1
    labels = [
        label.format(year=index // per_year, number=index % per_year + 1)
        for index in range(start, start + len(counts))
    ]
    return TransactionSeries(
        WARSZAWA,
        granularity,
        tuple(period(name, count) for name, count in zip(labels, counts, strict=True)),
    )


WARSZAWA_LAST_16_MONTHS = (
    *(1129, 1081, 1199, 1359, 1166, 1297, 1287, 1069, 1176, 1073, 1180, 1390),
    *(987, 22, 0, 35),
)
"""Transactions of Warsaw in 2025-04..2026-07 (``MONTHLY_WARSZAWA``): a year of usual
months, then 2026-04 (987, usual), 2026-05 (22), 2026-06 (0) and 2026-07 (35)."""


WARSZAWA_LAST_7_QUARTERS = (3105, 3483, 3902, 3605, 3721, 1034, 37)
"""Transactions of Warsaw in 2025-Q1..2026-Q3 (``QUARTERLY_WARSZAWA``): 2026-Q2 (1,034)
and 2026-Q3 (37) after about 3,700 a quarter."""


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
