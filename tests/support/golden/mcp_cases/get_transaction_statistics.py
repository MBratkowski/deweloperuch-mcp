"""The golden cases of the MCP tool ``get_transaction_statistics``
(tests/golden/mcp/<case>.json).
"""

from support.builders.transactions import month_rows, months, page_with_months, quarters
from support.golden.mcp import INJECTED, TX, Case, case, transactions_with
from support.providers.error_answers import removed_route
from support.providers.routes.transactions import (
    transaction_answer,
    transaction_routes,
    unknown_city_routes,
)

SAMPLE = transactions_with(monthly=months(3))
"""Three months of the sample page.stats_transactions.v2_view on the real page, and the
quarterly sample."""

CASES: dict[str, Case] = {
    # get_transaction_statistics: the samples (Warsaw), more periods as copies of their rows
    "transactions_months": case(TX, SAMPLE, city="warszawa"),
    # every month of Warsaw on 2026-10-31 (tests/fixtures/rsc/), with its incomplete tail
    "transactions_warszawa_20261031": case(TX, transaction_routes, city="warszawa"),
    "transactions_quarters": case(TX, SAMPLE, city="warszawa", granularity="quarter"),
    "transactions_67_months_periods_2": case(
        TX, transactions_with(monthly=months(67)), city="warszawa", periods=2
    ),
    "transactions_67_months_periods_60": case(
        TX, transactions_with(monthly=months(67)), city="warszawa", periods=60
    ),
    "transactions_39_quarters_periods_60": case(
        TX,
        transactions_with(quarterly=quarters(39)),
        city="warszawa",
        granularity="quarter",
        periods=60,
    ),
    "transactions_one_request_per_granularity": case(
        TX,
        SAMPLE,
        then=(
            (TX, {"city": "warszawa", "granularity": "quarter"}),
            (TX, {"city": "warszawa", "periods": 1}),
        ),
        city="warszawa",
    ),
    "transactions_granularity_null": case(TX, SAMPLE, city="warszawa", granularity=None),
    "transactions_granularity_blank": case(TX, SAMPLE, city="warszawa", granularity=""),
    "transactions_granularity_year": case(TX, SAMPLE, city="warszawa", granularity="year"),
    "transactions_periods_text": case(TX, SAMPLE, city="warszawa", periods="2"),
    "transactions_periods_61": case(TX, SAMPLE, city="warszawa", periods=61),
    "transactions_periods_true": case(TX, SAMPLE, city="warszawa", periods=True),
    "transactions_city_capitalized": case(TX, SAMPLE, city=" Warszawa "),
    "transactions_city_polska": case(TX, SAMPLE, city="polska"),
    "transactions_city_aggregate": case(TX, SAMPLE, city="7-miast"),
    "transactions_city_polish_letters": case(TX, SAMPLE, city="Kraków"),
    "transactions_city_path": case(TX, SAMPLE, city="warszawa/../x"),
    "transactions_without_city": case(TX, SAMPLE),
    # [P 2026-10-31] the page's 404 with a flight stream; [P 2026-10-30] the trend's JSON 404
    "transactions_unknown_city_404": case(TX, unknown_city_routes, city="nieistniejace-miasto"),
    "transactions_unknown_city_quarter_404": case(
        TX,
        transaction_answer(404, json={"error": INJECTED}),
        city="nieistniejace-miasto",
        granularity="quarter",
    ),
    "transactions_unknown_city_no_data": case(
        TX, transactions_with(monthly=page_with_months([])), city="nieistniejace-miasto"
    ),
    # D21: a removed page is a changed service, never an unknown city
    "transactions_removed_page": case(
        TX, transaction_answer(404, **removed_route()), city="warszawa"
    ),
    # a month that is not all of the secondary market: another series than described
    "transactions_another_market": case(
        TX,
        transactions_with(monthly=page_with_months([{**month_rows(1)[0], "secondary_count": 1}])),
        city="warszawa",
    ),
    "transactions_503": case(
        TX, transaction_answer(503, headers={"Retry-After": "10"}, text=INJECTED), city="warszawa"
    ),
    "transactions_403": case(TX, transaction_answer(403), city="warszawa"),
    "transactions_another_shape": case(
        TX, transaction_answer(200, json={INJECTED: True}), city="warszawa", granularity="quarter"
    ),
    "transactions_html": case(
        TX,
        transaction_answer(
            200, text=f"<html>{INJECTED}</html>", headers={"Content-Type": "text/html"}
        ),
        city="warszawa",
    ),
}
