"""The network of the tests: the mocked service and the event loop's sockets.

pytest-socket blocks every socket (``--disable-socket`` in pyproject.toml); these fixtures
never open the network, they only say what a test may use instead.
"""

import socket
from collections.abc import Iterator

import pytest
import respx

from support.checks.sockets import event_loop_sockets_only


@pytest.fixture
def service() -> Iterator[respx.MockRouter]:
    """The service, mocked: a request no route answers fails the test."""
    with respx.mock(assert_all_called=False, assert_all_mocked=True) as router:
        yield router


@pytest.fixture
def unix_sockets_for_the_event_loop() -> Iterator[None]:
    """asyncio's event loop needs a local socket pair (its self-pipe), so the modules that
    start the MCP server ask for this fixture (``pytestmark = usefixtures(...)``): Unix
    sockets on POSIX, a fixed loopback pair on Windows. Ordinary network sockets and
    DNS stay blocked (``test_network_stays_blocked``).
    pytest-socket restores its own setting after each test. Never autouse for the suite."""
    previous_pair = socket.socketpair
    event_loop_sockets_only()
    try:
        yield
    finally:
        socket.socketpair = previous_pair
