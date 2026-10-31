"""Contract of ``deweloperuch_mcp.api.dto.transaction_stats_page_dto`` with the service's
real answers: the prop ``view`` of the 2.0 statistics page (the samples in
docs/discovery/samples/, the whole RSC payloads of 2026-10-31 in tests/fixtures/rsc/).
"""

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from deweloperuch_mcp.api.dto.transaction_stats_page_dto import TransactionStatsPageDto
from deweloperuch_mcp.flight import component_props
from deweloperuch_mcp.models.government_statistics import PeriodCount
from deweloperuch_mcp.models.transaction_series import (
    Granularity,
    TransactionCity,
    TransactionPeriod,
    TransactionSeries,
)
from support.paths import API_FIXTURES
from support.providers.rsc import STATS_TX_KARPACZ_20261031, STATS_TX_WARSZAWA_20261031, raw
from support.providers.samples import body, envelope

PAGES = {"warszawa": STATS_TX_WARSZAWA_20261031, "karpacz": STATS_TX_KARPACZ_20261031}

SERIES_OF_1_0 = {
    "warszawa": API_FIXTURES / "monthly_tx_warszawa_20261015.json",
    "karpacz": API_FIXTURES / "monthly_tx_karpacz_20261016.json",
}
"""The monthly JSON series of 1.0 (``/api/monthly-transaction-stats``, removed on
2026-10-29), 2021-01 on."""


def props_of(page: Path) -> dict[str, Any]:
    """The first value of each prop of the page's client components."""
    found: dict[str, Any] = {}
    for name, value in component_props(raw(page)):
        found.setdefault(name, value)
    return found


def months_of(page: Path) -> tuple[TransactionPeriod, ...]:
    return TransactionStatsPageDto.model_validate(props_of(page)["view"]).to_model()


def test_the_sample_of_the_view() -> None:
    """page.stats_transactions.v2_view: the first three months of Warsaw, every field the
    DTO reads."""
    parsed = TransactionStatsPageDto.model_validate(body("page.stats_transactions.v2_view"))

    first = parsed.monthly[0]
    assert [row.month for row in parsed.monthly] == ["2017-01", "2017-02", "2017-03"]
    assert (first.transaction_count, first.secondary_count) == (890, 890)
    assert (first.med_price_sqm, first.avg_price_sqm) == (7656, 7903)
    assert (first.med_size, first.avg_size) == (47.9, 53.3)
    assert (first.med_amount, first.avg_amount) == (355000, 423836)
    assert parsed.to_model()[0] == TransactionPeriod(
        period="2017-01",
        transactions=890,
        median_price_per_m2=7656.0,
        average_price_per_m2=7903.0,
        median_area_m2=47.9,
        average_area_m2=53.3,
        median_price=355000.0,
        average_price=423836.0,
    )


def test_the_dto_refuses_trimming_markers() -> None:
    with pytest.raises(ValidationError):
        TransactionStatsPageDto.model_validate(envelope("page.stats_transactions.v2_view")["value"])


@pytest.mark.parametrize("city", list(PAGES))
def test_the_page_has_every_month_since_2017_to_the_current_one(city: str) -> None:
    """[P 2026-10-31] both pages: 118 rows, 2017-01..2026-10, one a month without a gap,
    the newest ones empty (Warszawa 3, Karpacz 10)."""
    rows = TransactionStatsPageDto.model_validate(props_of(PAGES[city])["view"]).monthly
    labels = [row.month for row in rows]

    expected = [f"{year}-{month:02d}" for year in range(2017, 2027) for month in range(1, 13)]
    assert labels == expected[:118]


@pytest.mark.parametrize(
    ("city", "count", "newest", "empty"),
    [("warszawa", 115, "2026-07", 1), ("karpacz", 108, "2025-12", 41)],
)
def test_the_months_end_with_the_newest_one_with_transactions(
    city: str, count: int, newest: str, empty: int
) -> None:
    """The empty months the page pads its end with are dropped (Warszawa 2026-08..2026-10,
    Karpacz 2026-01..2026-10); the empty months before the newest one with transactions
    stay (Warszawa 2026-06, 41 months of Karpacz)."""
    found = months_of(PAGES[city])

    assert (len(found), found[0].period, found[-1].period) == (count, "2017-01", newest)
    assert found[-1].transactions > 0
    assert sum(item.transactions == 0 for item in found) == empty


@pytest.mark.parametrize("city", list(SERIES_OF_1_0))
def test_the_months_are_the_series_of_1_0_four_years_longer(city: str) -> None:
    """Every month of the JSON series of 1.0 is on the page, so the rules calibrated on it
    hold: the counts revised by at most 2.4 % (Warsaw 2022-09: 967 on 2026-10-15, 944 here),
    the median price per m² by at most 0.2 %, the mean by at most 0.9 %; Karpacz equal but
    for the rounding. The page starts in 2017-01, the JSON series started in 2021-01; both
    end with the same month, the newest one with transactions."""
    old = json.loads(SERIES_OF_1_0[city].read_text(encoding="utf-8"))["data"]
    page = {item.period: item for item in months_of(PAGES[city])}

    assert (old[0]["month"], next(iter(page))) == ("2021-01", "2017-01")
    assert old[-1]["month"] == list(page)[-1]
    for row in old:
        new, count = page[row["month"]], row["transaction_count"]
        assert abs(new.transactions - count) <= 0.025 * count, row["month"]
        if count:
            assert new.median_price_per_m2 == pytest.approx(row["med_price_sqm"], rel=0.005)
            assert new.average_price_per_m2 == pytest.approx(row["avg_price_sqm"], rel=0.01)


def test_the_tail_of_warsaw() -> None:
    """2026-03 had 1,390 transactions in the JSON series of 1.0 and has 1,388 here; 2026-07
    35 with the median 33,176 per m² in both. Months without transactions have no
    measures, the others all six."""
    found = {item.period: item for item in months_of(STATS_TX_WARSZAWA_20261031)}

    assert found["2026-03"].transactions == 1388
    assert (found["2026-07"].transactions, found["2026-07"].median_price_per_m2) == (35, 33176)
    assert [label for label, item in found.items() if item.transactions == 0] == ["2026-06"]
    assert found["2026-06"].measures == (None,) * 6
    assert all(None not in item.measures for item in found.values() if item.transactions > 0)


def test_the_incomplete_tail_of_warsaw_ends_where_the_page_summarises() -> None:
    """The rules of the 1.0 series on the 2.0 one: 2026-05 (22), 2026-06 (0) and 2026-07
    (35) are incomplete, as in 1.0; 2026-04 (986) is the last complete month, the month the
    page itself summarises as its latest (``latestSummary``, which the client does not read:
    the rule that picks it is unknown)."""
    series = TransactionSeries(
        TransactionCity("warszawa"), Granularity.MONTH, months_of(STATS_TX_WARSZAWA_20261031)
    )

    found = series.latest(PeriodCount(118))

    assert [item.period for item in found.periods if item.incomplete] == [
        "2026-05",
        "2026-06",
        "2026-07",
    ]
    assert found.last_complete_period == "2026-04"
    assert props_of(STATS_TX_WARSZAWA_20261031)["latestSummary"]["month"] == "2026-04"
    assert found.few_transactions is False


def test_a_small_town_is_too_few_to_judge_and_the_page_summarises_nothing() -> None:
    """Karpacz: a median of 1 transaction a month, 41 months without any to 2025-12;
    nothing is flagged, no month is known to be complete, and the page has no
    ``latestSummary``."""
    karpacz = months_of(STATS_TX_KARPACZ_20261031)
    series = TransactionSeries(TransactionCity("karpacz"), Granularity.MONTH, karpacz)

    found = series.latest(PeriodCount(118))

    assert sum(item.transactions == 0 for item in karpacz) == 41
    assert all(item.measures == (None,) * 6 for item in karpacz if item.transactions == 0)
    assert not any(item.incomplete for item in found.periods)
    assert (found.last_complete_period, found.few_transactions) == (None, True)
    assert props_of(STATS_TX_KARPACZ_20261031)["latestSummary"] is None


@pytest.mark.parametrize("city", list(PAGES))
def test_the_page_is_the_secondary_market_of_flats(city: str) -> None:
    """[P 2026-10-31] what the tools say of the monthly series: in every month with
    transactions all of them are of the secondary market and none of an unknown one; a
    month without any has neither count (8 keys). The page says so itself: its lead
    („…na rynku wtórnym…”), ``propertyType`` and ``isMixedMarket``."""
    props = props_of(PAGES[city])
    rows = props["view"]["monthly"]

    with_data = [row for row in rows if row["transaction_count"] > 0]
    assert all(row["secondary_count"] == row["transaction_count"] for row in with_data)
    assert all(row["unknown_count"] == 0 for row in with_data)
    assert all(len(row) == 8 for row in rows if row["transaction_count"] == 0)
    assert "na rynku wtórnym" in props["lead"]
    assert (props["propertyType"], props["isMixedMarket"]) == ("mieszkania", False)


def test_the_median_and_the_mean_are_two_measures() -> None:
    """[W] ``med_*`` is read as the median and ``avg_*`` as the mean, by their names. They
    differ in every month of Warsaw; in Karpacz they are equal in every month of one or
    two transactions, as a median and a mean of so few are."""
    warszawa = [i for i in months_of(STATS_TX_WARSZAWA_20261031) if i.transactions > 0]
    karpacz = [i for i in months_of(STATS_TX_KARPACZ_20261031) if 0 < i.transactions <= 2]

    assert all(item.median_price_per_m2 != item.average_price_per_m2 for item in warszawa)
    assert karpacz
    assert all(item.median_price_per_m2 == item.average_price_per_m2 for item in karpacz)
