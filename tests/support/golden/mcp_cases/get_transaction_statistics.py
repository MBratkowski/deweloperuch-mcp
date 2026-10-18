"""The golden cases of the MCP tool ``get_transaction_statistics``
(tests/golden/mcp/<case>.json).
"""

from support.builders.transactions import months, quarters, warszawa_months
from support.golden.mcp import INJECTED, TX, Case, case, transactions_with
from support.providers.routes.transactions import transaction_answer, transaction_routes

CASES: dict[str, Case] = {
    # get_transaction_statistics: the samples (Warsaw), more periods as copies of their rows
    "transactions_months": case(TX, transaction_routes, city="warszawa"),
    # every month of Warsaw on 2026-10-15 (tests/fixtures/api/), with its incomplete tail
    "transactions_warszawa_20261015": case(
        TX, transactions_with(monthly=warszawa_months()), city="warszawa"
    ),
    "transactions_quarters": case(TX, transaction_routes, city="warszawa", granularity="quarter"),
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
        transaction_routes,
        then=(
            (TX, {"city": "warszawa", "granularity": "quarter"}),
            (TX, {"city": "warszawa", "periods": 1}),
        ),
        city="warszawa",
    ),
    "transactions_granularity_null": case(
        TX, transaction_routes, city="warszawa", granularity=None
    ),
    "transactions_granularity_blank": case(TX, transaction_routes, city="warszawa", granularity=""),
    "transactions_granularity_year": case(
        TX, transaction_routes, city="warszawa", granularity="year"
    ),
    "transactions_periods_text": case(TX, transaction_routes, city="warszawa", periods="2"),
    "transactions_periods_61": case(TX, transaction_routes, city="warszawa", periods=61),
    "transactions_periods_true": case(TX, transaction_routes, city="warszawa", periods=True),
    "transactions_city_capitalized": case(TX, transaction_routes, city=" Warszawa "),
    "transactions_city_polska": case(TX, transaction_routes, city="polska"),
    "transactions_city_polish_letters": case(TX, transaction_routes, city="Kraków"),
    "transactions_city_path": case(TX, transaction_routes, city="warszawa/../x"),
    "transactions_without_city": case(TX, transaction_routes),
    "transactions_unknown_city_404": case(
        TX, transaction_answer(404, json={"error": INJECTED}), city="nieistniejace-miasto"
    ),
    "transactions_unknown_city_no_data": case(
        TX,
        transaction_answer(200, json={"scope": {"label": "city"}, "data": []}),
        city="nieistniejace-miasto",
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
