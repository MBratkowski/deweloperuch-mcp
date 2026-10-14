"""Tests of ``deweloperuch_mcp.consumers.cli.support.formatting``."""

from deweloperuch_mcp.consumers.cli.support import formatting as cli_text


def test_numbers_have_no_negative_zero_and_no_unit_without_a_currency() -> None:
    assert cli_text.number_text(-0.001) == "0"
    assert cli_text.number_text(-0.004, 2, signed=True) == "0"
    assert cli_text.number_text(0.0, signed=True) == "0"
    assert cli_text.number_text(-5988, signed=True) == "-5 988"
    assert cli_text.number_text(0.01, 2, signed=True) == "+0,01"
    assert cli_text.number_text(1234567.5, 2) == "1 234 567,5"
    assert cli_text.amount_text(17991.17, cli_text.per_m2_unit(""), 2) == "17 991,17"
    assert cli_text.amount_text(None, cli_text.per_m2_unit(""), 2) == "?"
    assert cli_text.amount_text(None, cli_text.per_m2_unit("PLN"), 2) == "? PLN/m²"
