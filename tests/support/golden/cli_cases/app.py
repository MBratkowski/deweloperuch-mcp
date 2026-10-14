"""The golden cases of the CLI itself (help, no command, the command groups)
(tests/golden/cli/<case>.json).
"""

from support.golden.cli import Case, case

CASES: dict[str, Case] = {
    # help and usage
    "help": case("--help"),
    "no_arguments": case(),
    "help_locations": case("locations", "--help"),
    "help_offers": case("offers", "--help"),
    "help_investments": case("investments", "--help"),
    "help_developers": case("developers", "--help"),
    "help_stats": case("stats", "--help"),
    "help_stop": case("stop", "--help"),
    "help_valuation": case("valuation", "--help"),
    "help_skill": case("skill", "--help"),
    "unknown_command": case("transactions", "search"),
    # buildings get
    "help_buildings": case("buildings", "--help"),
}
