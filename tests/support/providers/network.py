"""The network of the tests: the mocked service and the event loop's sockets.

pytest-socket blocks every socket (``--disable-socket`` in pyproject.toml); these fixtures
never open the network, they only say what a test may use instead.
"""

from collections.abc import Iterator

import pytest
import pytest_socket
import respx


@pytest.fixture
def service() -> Iterator[respx.MockRouter]:
    """The service, mocked: a request no route answers fails the test."""
    with respx.mock(assert_all_called=False, assert_all_mocked=True) as router:
        yield router


@pytest.fixture
def unix_sockets_for_the_event_loop() -> Iterator[None]:
    """asyncio's event loop needs a local socket pair (its self-pipe), so the modules that
    start the MCP server ask for this fixture (``pytestmark = usefixtures(...)``): Unix
    sockets only, network sockets stay blocked (``test_network_stays_blocked``).
    pytest-socket restores its own setting after each test. Never autouse for the suite."""
    pytest_socket.enable_socket()
    pytest_socket.disable_socket(allow_unix_socket=True)
    yield
