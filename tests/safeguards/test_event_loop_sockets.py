"""Windows event-loop self-pipes work without allowing ordinary network access."""

import subprocess
import sys
from textwrap import dedent

import pytest

from support.paths import TESTS

INSTALLERS = {
    "fixture": "fixture = unix_sockets_for_the_event_loop.__wrapped__(); next(fixture)",
    "live_harness": "unix_sockets_only()",
    "stdio_child": "exec(no_network)",
    "fake_server_child": "exec(fake_server_bootstrap)",
}


@pytest.mark.parametrize("installer", INSTALLERS.values(), ids=INSTALLERS)
def test_windows_self_pipe_works_while_network_sockets_stay_blocked(installer: str) -> None:
    # Removing the native pair selects the real stdlib TCP fallback on POSIX too.
    # Platform spoofing lasts only for guard installation, before asyncio starts.
    script = dedent(
        f"""\
        import _socket
        if hasattr(_socket, "socketpair"):
            del _socket.socketpair
        import asyncio
        import runpy
        import socket
        import sys
        sys.path.insert(0, {str(TESTS)!r})
        import pytest_socket
        from support.providers.network import unix_sockets_for_the_event_loop
        from support.e2e.live import unix_sockets_only
        no_network = runpy.run_path({str(TESTS / "unit" / "test_mcp_server.py")!r})["NO_NETWORK"]
        fake_server = runpy.run_path(
            {str(TESTS / "safeguards" / "test_e2e_gate.py")!r}
        )["FAKE_SERVER"]
        fake_server_bootstrap = (
            fake_server.format(tests={str(TESTS)!r}).split("import respx\\n", 1)[0]
        )

        pytest_socket.disable_socket()
        platform = sys.platform
        sys.platform = "win32"
        try:
            {installer}
        finally:
            sys.platform = platform

        try:
            left, right = socket.socketpair()
        except PermissionError:
            if platform == "win32":
                raise
            sys.exit(77)  # The POSIX host sandbox forbids even a loopback bind.
        try:
            assert left.family == right.family == socket.AF_INET
            assert left.getsockname()[0] == right.getsockname()[0] == "127.0.0.1"
            left.settimeout(2)
            right.settimeout(2)
            right.sendall(b"local")
            assert left.recv(5) == b"local"
        finally:
            left.close()
            right.close()

        async def ready():
            await asyncio.sleep(0)
        asyncio.run(ready())
        print("event loop ready")

        for family in (socket.AF_INET, socket.AF_INET6):
            try:
                socket.socket(family, socket.SOCK_STREAM)
            except pytest_socket.SocketBlockedError:
                print("blocked", family.name)
            else:
                raise AssertionError("ordinary network socket allowed")
        for lookup, arguments in (
            (socket.getaddrinfo, ("localhost", 443)),
            (socket.gethostbyname, ("localhost",)),
        ):
            try:
                lookup(*arguments)
            except pytest_socket.SocketBlockedError:
                print("blocked", lookup.__name__)
            else:
                raise AssertionError("DNS allowed")
        """
    )

    done = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=30, check=False
    )

    if done.returncode == 77:
        pytest.skip("The POSIX host sandbox denies the Windows simulation's loopback bind")
    assert done.returncode == 0, done.stderr
    assert done.stdout.splitlines() == [
        "event loop ready",
        "blocked AF_INET",
        "blocked AF_INET6",
        "blocked _guarded_getaddrinfo",
        "blocked _guarded_gethostbyname",
    ]
