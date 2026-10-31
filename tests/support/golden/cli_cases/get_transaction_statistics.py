"""The golden cases of ``deweloperuch stats transactions`` (tests/golden/cli/<case>.json)."""

from typing import Any

import respx

from support.builders.transactions import months
from support.golden.cli import INJECTED, TX, Case, case
from support.providers.error_answers import removed_route
from support.providers.routes.transactions import (
    transaction_answer,
    transaction_routes,
    unknown_city_routes,
)


def sample_routes(router: respx.MockRouter) -> Any:
    """Three months of the sample page.stats_transactions.v2_view on the real page, and
    the quarterly sample."""
    return transaction_routes(router, monthly=months(3))


CASES: dict[str, Case] = {
    # stats transactions: the samples (Warsaw), more periods as copies of their rows
    "help_stats_transactions": case(*TX, "--help"),
    "stats_transactions_warszawa": case(*TX, "warszawa", service=sample_routes),
    # every month of Warsaw on 2026-10-31 (tests/fixtures/rsc/), with its incomplete tail
    "stats_transactions_warszawa_20261031": case(*TX, "warszawa", service=transaction_routes),
    "stats_transactions_warszawa_json": case(*TX, "warszawa", "--json", service=sample_routes),
    "stats_transactions_warszawa_quarter": case(
        *TX, "warszawa", "--granularity", "quarter", service=sample_routes
    ),
    "stats_transactions_warszawa_quarter_json": case(
        *TX, "warszawa", "--granularity", "quarter", "--json", service=sample_routes
    ),
    "stats_transactions_67_months_periods_2": case(
        *TX,
        "warszawa",
        "--periods",
        "2",
        service=lambda router: transaction_routes(router, monthly=months(67)),
    ),
    "stats_transactions_city_capitals": case(*TX, "Warszawa", service=sample_routes),
    "stats_transactions_polska": case(*TX, "polska", service=sample_routes),
    "stats_transactions_aggregate": case(*TX, "6-miast-bez-warszawy", service=sample_routes),
    "stats_transactions_polish_letters": case(*TX, "kraków", service=sample_routes),
    "stats_transactions_granularity_year": case(
        *TX, "warszawa", "--granularity", "year", service=sample_routes
    ),
    "stats_transactions_periods_0": case(*TX, "warszawa", "--periods", "0", service=sample_routes),
    # [P 2026-10-31] a city the page does not know: a 404 with a flight stream
    "stats_transactions_unknown_city": case(
        *TX, "nieistniejace-miasto", service=unknown_city_routes
    ),
    "stats_transactions_unknown_city_quarter": case(
        *TX,
        "nieistniejace-miasto",
        "--granularity",
        "quarter",
        service=transaction_answer(404, json={"error": INJECTED}),
    ),
    # D21: a removed page is a changed service (exit code 6), never an unknown city
    "stats_transactions_removed_page": case(
        *TX, "warszawa", service=transaction_answer(404, **removed_route())
    ),
    "stats_transactions_503": case(
        *TX, "warszawa", service=transaction_answer(503, headers={"Retry-After": "10"})
    ),
    "stats_transactions_403": case(*TX, "warszawa", service=transaction_answer(403)),
}
