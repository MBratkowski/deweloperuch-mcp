"""Stand-ins of probe's network: a transport with canned responses, an HTTPS handler,
sockets and bodies that arrive in chunks or fail.
"""

import email.message
import http.client
import io
import urllib.request
import urllib.response
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

import probe


@dataclass
class FakeProbeService:
    """Mocked transport: hands out canned responses and records every request."""

    responses: list[probe.Response]
    requests: list[tuple[str, dict[str, str], float]] = field(default_factory=list)
    on_request: Callable[[], object] | None = None

    def __call__(self, url: str, headers: Mapping[str, str], timeout: float) -> probe.Response:
        self.requests.append((url, dict(headers), timeout))
        if self.on_request is not None:
            self.on_request()
        return self.responses.pop(0)


class InMemoryHTTPS(urllib.request.BaseHandler):
    """urllib handler that answers https requests from memory, before the real one."""

    handler_order = 100

    def __init__(
        self, *replies: tuple[int, dict[str, str], bytes | io.BytesIO | http.client.HTTPResponse]
    ) -> None:
        self.replies = list(replies)
        self.requests: list[urllib.request.Request] = []

    def https_open(self, req: urllib.request.Request) -> urllib.response.addinfourl:
        self.requests.append(req)
        status, headers, body = self.replies.pop(0)
        message = email.message.Message()
        for name, value in headers.items():
            message[name] = value
        stream = io.BytesIO(body) if isinstance(body, bytes) else body
        reply = urllib.response.addinfourl(stream, message, req.full_url, status)
        reply.msg = "reason"  # type: ignore[attr-defined]  # read by HTTPErrorProcessor
        return reply


class ChunkedHTTPResponse:
    """A body stream that serves ``chunk`` ``count`` times, then EOF or ``then``.

    The fake clock ticks once per read.
    """

    def __init__(
        self, chunk: bytes, count: int, tick: float = 0.0, then: Exception | None = None
    ) -> None:
        self.chunk, self.count, self.tick, self.then = chunk, count, tick, then
        self.now = 0.0
        self.reads = 0

    def read1(self, size: int, /) -> bytes:
        self.reads += 1
        self.now += self.tick
        if self.count == 0:
            if self.then is not None:
                raise self.then
            return b""
        self.count -= 1
        return self.chunk[:size]

    def clock(self) -> float:
        return self.now


class SocketFromBytes:
    """Enough of a socket for http.client.HTTPResponse to parse ``data`` (no network)."""

    def __init__(self, data: bytes) -> None:
        self.data = data

    def makefile(self, mode: str) -> io.BytesIO:
        return io.BytesIO(self.data)


class FailingBody(io.BytesIO):
    """A body whose first read returns ``prefix`` and whose next read fails."""

    def __init__(self, prefix: bytes, error: Exception) -> None:
        super().__init__(prefix)
        self.error = error

    def read1(self, size: int | None = -1, /) -> bytes:
        chunk = super().read1(size)
        if not chunk:
            raise self.error
        return chunk
