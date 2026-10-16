"""Allow asyncio's local self-pipe while pytest-socket keeps network access blocked."""

import socket
import sys

import pytest_socket


def _loopback_socketpair(
    family: int | None = None, type: int = socket.SOCK_STREAM, proto: int = 0
) -> tuple[socket.socket, socket.socket]:
    """A fixed IPv4 loopback pair for Windows, with no caller-selected address.

    The stdlib fallback uses the globally guarded constructor, including when accept()
    wraps its descriptor. Use pytest-socket's saved constructor locally instead; neither
    the socket constructor nor DNS guards are lifted while creating the pair.
    """
    if family not in (None, socket.AF_INET) or type != socket.SOCK_STREAM or proto != 0:
        raise ValueError("Only an IPv4 TCP socket pair with protocol zero is allowed")

    real_socket = pytest_socket._true_socket
    with real_socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.settimeout(5)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        connector = real_socket(socket.AF_INET, socket.SOCK_STREAM)
        accepted = None
        try:
            connector.settimeout(5)
            connector.connect(listener.getsockname())
            # socket.accept() uses this raw primitive before wrapping the descriptor.
            descriptor, _ = listener._accept()  # type: ignore[attr-defined]
            try:
                accepted = real_socket(socket.AF_INET, socket.SOCK_STREAM, fileno=descriptor)
            except BaseException:
                socket.close(descriptor)
                raise
            # Like the stdlib fallback, reject a connection from an unexpected peer.
            if (
                accepted.getsockname() != connector.getpeername()
                or connector.getsockname() != accepted.getpeername()
            ):
                raise ConnectionError("Unexpected peer connection in the event-loop socket pair")
            accepted.settimeout(socket.getdefaulttimeout())
            connector.settimeout(socket.getdefaulttimeout())
            return accepted, connector
        except BaseException:
            connector.close()
            if accepted is not None:
                accepted.close()
            raise


def event_loop_sockets_only() -> None:
    """Install the ordinary guard plus Windows' fixed local socket-pair exception."""
    # disable_socket subclasses the current constructor: reset before replacing a guard.
    pytest_socket.enable_socket()
    pytest_socket.disable_socket(allow_unix_socket=True)
    if sys.platform == "win32":
        socket.socketpair = _loopback_socketpair
