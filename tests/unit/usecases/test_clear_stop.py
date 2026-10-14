"""Tests of ``deweloperuch_mcp.usecases.clear_stop``."""

from deweloperuch_mcp.usecases.clear_stop import ClearStop, ClearStopRequest
from deweloperuch_mcp.usecases.get_stop_status import GetStopStatus, GetStopStatusRequest
from support.fakes.stop import FakeStopControl


def test_stop_use_cases_pass_the_state_on() -> None:
    control = FakeStopControl()

    status = GetStopStatus(control).execute(GetStopStatusRequest.parse())
    cleared = ClearStop(control).execute(ClearStopRequest.parse(wait_limit=1.0, notice_after=0.5))

    assert status.state == "state"
    assert cleared.before == "before"
    assert control.cleared == [(1.0, 0.5, None)]
