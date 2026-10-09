"""Guards the test configuration: pytest-socket must block network access (D10)."""

import socket

import pytest
from pytest_socket import SocketBlockedError


# The warning is the expected effect here; elsewhere it still flags a real attempt.
@pytest.mark.filterwarnings("ignore:A test tried to use socket.socket:UserWarning")
def test_sockets_are_blocked() -> None:
    with pytest.raises(SocketBlockedError):
        socket.socket(socket.AF_INET, socket.SOCK_STREAM)
