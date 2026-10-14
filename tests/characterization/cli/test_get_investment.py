"""Golden cases of ``deweloperuch investments get``: tests/golden/cli/<case>.json."""

import pytest
import respx

from support.golden.cli import check_case
from support.golden.cli_cases.get_investment import CASES


@pytest.mark.parametrize("name", CASES)
def test_cli_output_is_the_recorded_one(name: str, service: respx.MockRouter) -> None:
    check_case(name, CASES[name], service)
