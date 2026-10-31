"""Test data of the transaction statistics. Payloads are the whole real answers of
tests/fixtures/ (the 2.0 statistics page of a city as RSC, ``warszawa_page``; the
quarterly trend of Warsaw, ``warszawa_quarters``) or are derived from real rows (copies
of a sample's rows with new labels, never values made up; months are spliced into the
real page, ``page_with_months``); the domain objects, page addresses and expected texts
here are the ones several test modules share.
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
from support.providers.rsc import (
    STATS_TX_KARPACZ_20261031,
    STATS_TX_WARSZAWA_20261031,
    prop_value_span,
    raw,
    replace_prop,
)
from support.providers.samples import body
from support.providers.service import BASE


def _labels(first_year: int, count: int, per_year: int, label: str) -> list[str]:
    return [
        label.format(year=first_year + index // per_year, number=index % per_year + 1)
        for index in range(count)
    ]


# --- months: the statistics page of a city (2.0) ----------------------------------------------


def warszawa_page() -> bytes:
    """Every month of Warsaw (2017-01..2026-10) on the statistics page, byte for byte as
    the service sent it on 2026-10-31, with the real tail of incomplete months
    (tests/fixtures/rsc/README.md)."""
    return raw(STATS_TX_WARSZAWA_20261031)


def karpacz_page() -> bytes:
    """Every month of Karpacz (2017-01..2026-10), a small town, as sent on 2026-10-31: a
    median of 1 transaction a month, 51 months without any, ``latestSummary`` null."""
    return raw(STATS_TX_KARPACZ_20261031)


def warszawa_rows() -> list[dict[str, Any]]:
    """The rows of ``view.monthly`` of ``warszawa_page``, parsed."""
    rows: list[dict[str, Any]] = _view(warszawa_page())["monthly"]
    return rows


def page_with_months(monthly: list[dict[str, Any]]) -> bytes:
    """The real page of Warsaw with these rows as ``view.monthly``; every other byte as
    sent (the value sits in a row that ends with a newline, and the page has no text rows,
    so no byte length in the stream changes)."""
    payload = warszawa_page()
    return replace_prop(payload, "view", lambda _: True, {**_view(payload), "monthly": monthly})


def month_rows(count: int) -> list[dict[str, Any]]:
    """``count`` months from 2017-01 as the page sends them: copies of the three rows of
    the sample page.stats_transactions.v2_view (Warsaw, 2017-01..2017-03, 890, 880 and
    1,086 transactions) with new labels."""
    rows = body("page.stats_transactions.v2_view")["monthly"]
    return [
        {**copy.deepcopy(rows[index % len(rows)]), "month": label}
        for index, label in enumerate(_labels(2017, count, 12, "{year}-{number:02d}"))
    ]


def months(count: int) -> bytes:
    """The page of Warsaw with ``count`` months from 2017-01 (``month_rows``)."""
    return page_with_months(month_rows(count))


def _view(payload: bytes) -> dict[str, Any]:
    start, end = prop_value_span(payload, "view")
    view: dict[str, Any] = json.loads(payload[start:end])
    return view


# [P 2026-10-13] live observation (Warsaw 2026-05/06, the JSON series of 1.0): no
# transactions, every measure 0. [P 2026-10-31] the 2.0 page sends such a month the same
# way, without `secondary_count` and `unknown_count` (Warsaw 2026-06, 2026-08..2026-10).
ZERO_MONTH = {
    "transaction_count": 0,
    "med_price_sqm": 0,
    "avg_price_sqm": 0,
    "med_size": 0,
    "avg_size": 0,
    "med_amount": 0,
    "avg_amount": 0,
}


def zero_month(label: str) -> dict[str, Any]:
    """A month without transactions as the page sends it: 8 keys, every measure 0."""
    return {"month": label, **ZERO_MONTH}


# --- quarters: the trend of a city ---------------------------------------------------------------


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


QUARTERLY_WARSZAWA = API_FIXTURES / "avg_trend_city_warszawa_20261016.json"
"""Every quarter of Warsaw (2017-Q1..2026-Q3) as the service sent them on 2026-10-16."""


def warszawa_quarters() -> Any:
    """The whole body of ``QUARTERLY_WARSZAWA``, parsed."""
    return json.loads(QUARTERLY_WARSZAWA.read_text(encoding="utf-8"))


# --- the domain -----------------------------------------------------------------------------------


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
"""Transactions of Warsaw in 2025-04..2026-07 as the JSON series of 1.0 had them
(tests/fixtures/api/monthly_tx_warszawa_20261015.json): a year of usual months, then
2026-04 (987, usual), 2026-05 (22), 2026-06 (0) and 2026-07 (35). The 2.0 page of
2026-10-31 differs by at most 2 a month (2026-03 1,388, 2026-04 986) and pads the months
after 2026-07 with zeros, which the client drops: its series ends with 2026-07 too."""


WARSZAWA_LAST_7_QUARTERS = (3105, 3483, 3902, 3605, 3721, 1034, 37)
"""Transactions of Warsaw in 2025-Q1..2026-Q3 (``QUARTERLY_WARSZAWA``): 2026-Q2 (1,034)
and 2026-Q3 (37) after about 3,700 a quarter."""


def stats_page(city: str) -> str:
    """The page ``stats_url`` points to: the transaction statistics of ``city``, moved to
    ``/statystyki/{city}/transakcje`` by the 2.0 service [P 2026-10-30]; the page the
    monthly series is read from."""
    return f"{BASE}/statystyki/{city}/transakcje"
