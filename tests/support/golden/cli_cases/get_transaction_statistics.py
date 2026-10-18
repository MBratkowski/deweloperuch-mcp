"""The golden cases of ``deweloperuch stats transactions`` (tests/golden/cli/<case>.json)."""

from support.builders.transactions import months, warszawa_months
from support.golden.cli import INJECTED, TX, Case, case
from support.providers.routes.transactions import transaction_answer, transaction_routes

CASES: dict[str, Case] = {
    # stats transactions: the samples (Warsaw), more periods as copies of their rows
    "help_stats_transactions": case(*TX, "--help"),
    "stats_transactions_warszawa": case(*TX, "warszawa", service=transaction_routes),
    # every month of Warsaw on 2026-10-15 (tests/fixtures/api/), with its incomplete tail
    "stats_transactions_warszawa_20261015": case(
        *TX,
        "warszawa",
        service=lambda router: transaction_routes(router, monthly=warszawa_months()),
    ),
    "stats_transactions_warszawa_json": case(*TX, "warszawa", "--json", service=transaction_routes),
    "stats_transactions_warszawa_quarter": case(
        *TX, "warszawa", "--granularity", "quarter", service=transaction_routes
    ),
    "stats_transactions_warszawa_quarter_json": case(
        *TX, "warszawa", "--granularity", "quarter", "--json", service=transaction_routes
    ),
    "stats_transactions_67_months_periods_2": case(
        *TX,
        "warszawa",
        "--periods",
        "2",
        service=lambda router: transaction_routes(router, monthly=months(67)),
    ),
    "stats_transactions_city_capitals": case(*TX, "Warszawa", service=transaction_routes),
    "stats_transactions_polska": case(*TX, "polska", service=transaction_routes),
    "stats_transactions_polish_letters": case(*TX, "kraków", service=transaction_routes),
    "stats_transactions_granularity_year": case(
        *TX, "warszawa", "--granularity", "year", service=transaction_routes
    ),
    "stats_transactions_periods_0": case(
        *TX, "warszawa", "--periods", "0", service=transaction_routes
    ),
    "stats_transactions_unknown_city": case(
        *TX, "nieistniejace-miasto", service=transaction_answer(404, json={"error": INJECTED})
    ),
    "stats_transactions_503": case(
        *TX, "warszawa", service=transaction_answer(503, headers={"Retry-After": "10"})
    ),
    "stats_transactions_403": case(*TX, "warszawa", service=transaction_answer(403)),
}
