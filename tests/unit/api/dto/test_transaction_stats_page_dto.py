"""Tests of ``deweloperuch_mcp.api.dto.transaction_stats_page_dto``: the rules of a month
and of the months of a page, on the real rows of the sample page.stats_transactions.v2_view,
edited where a test is about a shape."""

from typing import Any

import pytest
from pydantic import ValidationError

from deweloperuch_mcp.api.dto.transaction_stats_page_dto import (
    OTHER_MARKET,
    TransactionStatsPageDto,
)
from deweloperuch_mcp.models.errors import SERVICE_CHANGED, UnexpectedResponseError
from deweloperuch_mcp.models.transaction_series import TransactionPeriod
from support.builders.transactions import month_rows, zero_month


def view(*rows: dict[str, Any]) -> dict[str, Any]:
    return {"monthly": list(rows)}


def months(*rows: dict[str, Any]) -> tuple[TransactionPeriod, ...]:
    return TransactionStatsPageDto.model_validate(view(*rows)).to_model()


def with_data(label: str) -> dict[str, Any]:
    """A month with transactions: a row of the sample under another label."""
    return {**month_rows(1)[0], "month": label}


def test_a_month_without_transactions_inside_the_series_is_kept_without_measures() -> None:
    """[P 2026-10-31] the page's own shape of such a month: 8 keys, every measure 0."""
    found = months(with_data("2017-01"), zero_month("2017-02"), with_data("2017-03"))

    assert found[1] == TransactionPeriod("2017-02", 0)
    assert found[1].measures == (None,) * 6


def test_the_empty_months_after_the_newest_one_with_transactions_are_dropped() -> None:
    """The page pads its end with empty months; every one of them goes, none before the
    newest month with transactions (Warsaw keeps its empty 2026-06)."""
    found = months(
        with_data("2017-01"),
        zero_month("2017-02"),
        with_data("2017-03"),
        zero_month("2017-04"),
        zero_month("2017-05"),
    )

    assert [item.period for item in found] == ["2017-01", "2017-02", "2017-03"]


def test_the_padding_is_dropped_in_any_order_of_the_rows() -> None:
    """The newest month with transactions ends the series, wherever its row is."""
    found = months(zero_month("2017-05"), with_data("2017-03"), zero_month("2017-02"))

    assert sorted(item.period for item in found) == ["2017-02", "2017-03"]


@pytest.mark.parametrize("rows", [(), (zero_month("2017-01"), zero_month("2017-02"))])
def test_a_page_without_transactions_has_no_months(rows: tuple[dict[str, Any], ...]) -> None:
    """No month to show: the series is empty, which the domain reports as a city without
    data."""
    assert months(*rows) == ()


@pytest.mark.parametrize("secondary", [889, 0])
def test_a_month_with_transactions_of_another_market_is_refused_with_its_own_message(
    secondary: int,
) -> None:
    """The months are described as the secondary market: a month whose transactions are
    not all of it is another series, said as such, not as a changed service."""
    with pytest.raises(UnexpectedResponseError) as caught:
        months({**with_data("2017-01"), "secondary_count": secondary})

    assert str(caught.value) == OTHER_MARKET
    assert SERVICE_CHANGED not in str(caught.value)
    assert caught.value.detail == (
        f"prop view, miesiąc 2017-01: {secondary} z 890 transakcji z rynku wtórnego"
    )


def test_the_message_of_another_market_says_what_to_do() -> None:
    assert OTHER_MARKET == (
        "Miesięczne dane serwisu obejmują też transakcje spoza rynku wtórnego, a to narzędzie "
        "podaje tylko rynek wtórny, więc nie zwraca tego szeregu. To nie znaczy, że argumenty "
        "są błędne: nie zmieniaj ich i nie ponawiaj wywołania, powiedz o tym użytkownikowi. "
        "Kwartały (granularity=quarter) idą z innego źródła, ale ich rynek jest nieokreślony."
    )


@pytest.mark.parametrize(
    "row",
    [
        {k: v for k, v in month_rows(1)[0].items() if k != "secondary_count"},  # key missing
        {**month_rows(1)[0], "secondary_count": 891},  # more than all of them
        {**zero_month("2017-01"), "secondary_count": 3},  # some of none
    ],
)
def test_counts_of_the_market_off_the_contract_are_a_changed_page(row: dict[str, Any]) -> None:
    """Not another market but a page that no longer says it: a contract mismatch (the
    transport's changed-service message), never a count read as 0."""
    with pytest.raises(ValidationError):
        months(row)


def test_the_count_of_an_unknown_market_is_not_read() -> None:
    """Only ``secondary_count`` against ``transaction_count`` tells the market."""
    assert months({**month_rows(1)[0], "unknown_count": "?"})[0].transactions == 890


@pytest.mark.parametrize(
    "change",
    [
        {"month": "2017-1"},
        {"month": "2017-Q1"},
        {"transaction_count": "dużo"},
        {"med_price_sqm": "dużo"},
        {"avg_size": [1]},
    ],
)
def test_a_month_off_the_contract_is_refused(change: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        months({**month_rows(1)[0], **change})


@pytest.mark.parametrize("missing", ["month", "transaction_count", "med_price_sqm", "avg_amount"])
def test_every_field_read_is_required(missing: str) -> None:
    row = month_rows(1)[0]
    del row[missing]

    with pytest.raises(ValidationError):
        months(row)


def test_a_view_without_months_is_refused() -> None:
    with pytest.raises(ValidationError):
        TransactionStatsPageDto.model_validate({"anchor": "2026-Q1", "quarterly": {}})
