"""The golden cases of ``deweloperuch investments search`` (tests/golden/cli/<case>.json)."""

from support.golden.cli import SEARCH, Case, case
from support.golden.routes import search_answer, search_city_is
from support.providers.routes.investment_search import investment_search_routes

CASES: dict[str, Case] = {
    "help_investments_search": case("investments", "search", "--help"),
    # investments search
    "investments_search": case(*SEARCH, "sopot", service=investment_search_routes),
    "investments_search_json": case(*SEARCH, "sopot", "--json", service=investment_search_routes),
    "investments_search_by_name": case(
        *SEARCH, "--name", "nowy targ", service=investment_search_routes
    ),
    "investments_search_by_name_json": case(
        *SEARCH, "--name", "nowy targ", "--json", service=investment_search_routes
    ),
    "investments_search_every_option": case(
        *SEARCH,
        "sopot",
        "--name",
        "KOLIBKI",
        "--developer",
        "invest-komfort-spolka-akcyjna",
        "--sort",
        "price_per_m2_desc",
        "--limit",
        "1",
        service=investment_search_routes,
    ),
    "investments_search_many_limit_5": case(
        *SEARCH, "sopot", "--sort", "name", "--limit", "5", service=search_city_is(60)
    ),
    "investments_search_nothing": case(*SEARCH, "sopot", service=search_city_is(0)),
    "investments_search_filters_match_nothing": case(
        *SEARCH, "sopot", "--developer", "atal", service=investment_search_routes
    ),
    "investments_search_without_arguments": case(*SEARCH, service=investment_search_routes),
    "investments_search_polska": case(*SEARCH, "polska", service=investment_search_routes),
    "investments_search_city_capitals": case(*SEARCH, "Sopot", service=investment_search_routes),
    "investments_search_name_too_short": case(*SEARCH, "--name", "k"),
    "investments_search_developer_without_city": case(
        *SEARCH, "--name", "kolibki", "--developer", "atal"
    ),
    "investments_search_sort_without_city": case(*SEARCH, "--name", "kolibki", "--sort", "name"),
    "investments_search_sort_unknown": case(*SEARCH, "sopot", "--sort", "cheap"),
    "investments_search_limit_0": case(*SEARCH, "sopot", "--limit", "0"),
    "investments_search_404": case(*SEARCH, "sopot", service=search_answer(404)),
    "investments_search_500": case(*SEARCH, "sopot", service=search_answer(500, text="x")),
    "investments_search_403": case(*SEARCH, "sopot", service=search_answer(403)),
    "investments_search_another_shape": case(
        *SEARCH, "sopot", service=search_answer(200, json={"unexpected": True})
    ),
}
