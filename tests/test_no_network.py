"""Guards the test configuration: pytest-socket must block network access (D10), and
the user's real cache stays out of reach."""

import socket
from pathlib import Path

import pytest
from pytest_socket import SocketBlockedError

from deweloperuch_mcp.throttle import RequestLimiter, default_lock_dir


# The warning is the expected effect here; elsewhere it still flags a real attempt.
@pytest.mark.filterwarnings("ignore:A test tried to use socket.socket:UserWarning")
def test_sockets_are_blocked() -> None:
    with pytest.raises(SocketBlockedError):
        socket.socket(socket.AF_INET, socket.SOCK_STREAM)


def test_tests_never_use_the_real_cache(tmp_path_factory: pytest.TempPathFactory) -> None:
    """tests/conftest.py: the limiter's default directory (its lock and the STOP record)
    and the scanner's chunk cache are under the test's own temporary XDG_CACHE_HOME."""
    lock_dir = default_lock_dir()

    assert lock_dir.is_relative_to(tmp_path_factory.getbasetemp())
    assert not lock_dir.is_relative_to(Path.home() / ".cache")
    assert RequestLimiter().stop_path.parent == lock_dir
