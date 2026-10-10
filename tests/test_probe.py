"""recon/probe.py: one allowlisted, rate-limited GET per run, on a mocked transport.

Nothing here reaches the network: requests go to ``FakeService`` (injected ``fetch``) or,
for the urllib transport itself, to a urllib handler that answers in memory. Samples
are written to a temporary directory, never to docs/discovery/samples/.
"""

import ast
import copy
import email.message
import fcntl
import hashlib
import http.client
import io
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
import urllib.response
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date
from email.utils import formatdate
from pathlib import Path
from typing import Any

import pytest

import http_common
import probe
from deweloperuch_mcp import identity
from deweloperuch_mcp.throttle import (
    LOCK_FILENAME,
    MAX_DEFER,
    STOP_FILENAME,
    RequestLimiter,
    Slot,
    StopRecord,
)
from rsc_fixtures import OFFERS_UNKNOWN_CITY, OFFERS_WARSZAWA, raw

REPO = Path(__file__).resolve().parent.parent
PROBE = REPO / "recon" / "probe.py"
SAMPLES = REPO / "docs" / "discovery" / "samples"

# Assembled in code: the repo does not carry ready-to-paste service addresses.
HOST = "deweloperuch" + ".pl"
CAPTURED = date(2026, 10, 9)  # `_captured` of the existing samples
NOW = 1_800_000_000.0

USAGE, STOP, HTTP_ERROR, WAIT, NO_DATA = 2, 3, 4, 5, 6


# --- test doubles ----------------------------------------------------------------


@dataclass
class FakeService:
    """Mocked transport: hands out canned responses and records every request."""

    responses: list[probe.Response]
    requests: list[tuple[str, dict[str, str], float]] = field(default_factory=list)
    on_request: Callable[[], object] | None = None

    def __call__(self, url: str, headers: Mapping[str, str], timeout: float) -> probe.Response:
        self.requests.append((url, dict(headers), timeout))
        if self.on_request is not None:
            self.on_request()
        return self.responses.pop(0)


@dataclass
class Env:
    limiter: RequestLimiter
    lock_dir: Path
    samples_dir: Path

    def run(self, argv: list[str], service: Callable[..., probe.Response], **kw: Any) -> int:
        kw.setdefault("today", CAPTURED)
        return probe.main(
            argv, fetch=service, limiter=self.limiter, samples_dir=self.samples_dir, **kw
        )

    def pause_after_last_request(self) -> float:
        state = json.loads((self.lock_dir / LOCK_FILENAME).read_text())
        return float(state["next_start"] - state["last_end"])


@pytest.fixture
def env(tmp_path: Path) -> Env:
    lock_dir = tmp_path / "lock"
    samples_dir = tmp_path / "samples"
    samples_dir.mkdir()
    # min_interval=0 keeps the suite fast; any pause in the lock file comes from defer().
    limiter = RequestLimiter(lock_dir, min_interval=0, testing_only_allow_fast_interval=True)
    return Env(limiter, lock_dir, samples_dir)


def response(
    status: int = 200, body: bytes = b"", content_type: str = "", **headers: str
) -> probe.Response:
    names = {key.replace("_", "-").lower(): value for key, value in headers.items()}
    if content_type:
        names["content-type"] = content_type
    return probe.Response(status, names, body)


def json_response(data: Any, status: int = 200, **headers: str) -> probe.Response:
    body = json.dumps(data, ensure_ascii=False).encode()
    return response(status, body, "application/json; charset=utf-8", **headers)


def rsc_text(props: Mapping[str, Any]) -> str:
    """A raw RSC response with one client component carrying ``props``.

    Compact JSON, as on the wire: find_json_after expects the value right after the colon.
    """
    encoded = json.dumps(dict(props), ensure_ascii=False, separators=(",", ":"))
    return (
        '0:{"P":null,"b":"build-id","p":"","i":false}\n'
        '1:I[4242,["static/chunks/4242.js"],"Client"]\n'
        f'2:["$","div",null,{{"className":"page","children":["$","$L1",null,{encoded}]}}]\n'
    )


def rsc_response(props: Mapping[str, Any]) -> probe.Response:
    return response(200, rsc_text(props).encode(), "text/x-component")


CHALLENGE_HTML = (
    b"<!DOCTYPE html><html><head><title>Just a moment...</title></head>"
    b"<body><script>window._cf_chl_opt={cType:'managed'};</script></body></html>"
)

MARKER = re.compile(r"\.\.\. \((\d+) more, (\d+) total\)")


def untrim(value: Any) -> Any:
    """Undo sample trimming: each "... (N more, M total)" becomes N copies of the last item."""
    if isinstance(value, list):
        items = [untrim(item) for item in value]
        if items and isinstance(value[-1], str) and (marker := MARKER.fullmatch(value[-1])):
            items.pop()
            items += [copy.deepcopy(items[-1]) for _ in range(int(marker[1]))]
        return items
    if isinstance(value, dict):
        return {key: untrim(item) for key, item in value.items()}
    return value


def load_sample(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((SAMPLES / name).read_text(encoding="utf-8"))
    return data


# --- request: URL, headers, transport ---------------------------------------------


def test_api_request_is_one_get_with_shared_user_agent(
    env: Env, capsys: pytest.CaptureFixture[str]
) -> None:
    service = FakeService([json_response({"city": "Warszawa", "city_slug": "warszawa"})])

    code = env.run(["api", "/api/city-lookup?city=warszawa"], service)

    assert code == 0
    assert service.requests == [
        (
            identity.BASE_URL + "/api/city-lookup?city=warszawa",
            {"User-Agent": identity.USER_AGENT, "Accept": "application/json"},
            probe.TIMEOUT,
        )
    ]
    assert json.loads(capsys.readouterr().out) == {"city": "Warszawa", "city_slug": "warszawa"}


def test_query_is_percent_encoded_and_existing_escapes_are_kept(env: Env) -> None:
    service = FakeService([json_response({})])

    env.run(["api", "/api/investments?q=nowy%20targ&limit=5&x=Mokotów ok&p=100%"], service)

    url = service.requests[0][0]
    assert url == (
        identity.BASE_URL + "/api/investments?q=nowy%20targ&limit=5&x=Mokot%C3%B3w%20ok&p=100%25"
    )


def rsc_token(target: str) -> str:
    return hashlib.sha256(target.encode()).hexdigest()[:8]


def test_page_sends_rsc_header_and_deterministic_rsc_token(env: Env) -> None:
    path = "/ceny-ofertowe/warszawa/mieszkania?perPage=100&sortBy=amount"
    service = FakeService([rsc_response({"initialData": {}})] * 2)

    env.run(["page", path, "--prop", "initialData"], service)
    env.run(["page", path, "--prop", "initialData"], service)

    (url, headers, _), again = service.requests
    assert url == f"{identity.BASE_URL}{path}&_rsc={rsc_token(path)}"
    assert again[0] == url
    assert headers == {"User-Agent": identity.USER_AGENT, "RSC": "1"}


def test_rsc_token_depends_on_path_and_query(env: Env) -> None:
    paths = [
        "/ceny-ofertowe/warszawa/mieszkania",
        "/ceny-ofertowe/warszawa/mieszkania?page=2",
        "/ceny-ofertowe/krakow/mieszkania",
    ]
    service = FakeService([rsc_response({"initialData": {}}) for _ in paths])

    for path in paths:
        env.run(["page", path, "--prop", "initialData"], service)

    urls = [url for url, _, _ in service.requests]
    assert urls[0] == f"{identity.BASE_URL}{paths[0]}?_rsc={rsc_token(paths[0])}"
    assert len({url.rsplit("_rsc=", 1)[1] for url in urls}) == 3


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


@pytest.fixture
def https(monkeypatch: pytest.MonkeyPatch) -> Callable[..., InMemoryHTTPS]:
    """Routes probe's urllib opener to an InMemoryHTTPS with the given replies."""
    real_build_opener = urllib.request.build_opener

    def install(*replies: tuple[int, dict[str, str], bytes]) -> InMemoryHTTPS:
        handler = InMemoryHTTPS(*replies)

        def build_opener(*handlers: Any) -> urllib.request.OpenerDirector:
            return real_build_opener(*handlers, handler)

        monkeypatch.setattr(urllib.request, "build_opener", build_opener)
        return handler

    return install


def test_urllib_transport_sends_user_agent(
    env: Env, https: Callable[..., InMemoryHTTPS], capsys: pytest.CaptureFixture[str]
) -> None:
    server = https((200, {"Content-Type": "application/json"}, b'{"count": 13324}'))

    code = probe.main(
        ["api", "/api/offer-count?city=warszawa"],
        limiter=env.limiter,
        samples_dir=env.samples_dir,
    )

    assert code == 0
    (request,) = server.requests
    assert request.full_url == identity.BASE_URL + "/api/offer-count?city=warszawa"
    assert request.get_method() == "GET"
    assert request.get_header("User-agent") == identity.USER_AGENT
    assert request.timeout == probe.TIMEOUT
    assert json.loads(capsys.readouterr().out) == {"count": 13324}


def test_urllib_transport_does_not_follow_redirects(https: Callable[..., InMemoryHTTPS]) -> None:
    server = https(
        (302, {"Location": "https://example.com/elsewhere"}, b""),
        (200, {}, b"followed"),
    )

    reply = probe.urllib_fetch(identity.BASE_URL + "/api/cities", {}, 5.0)

    assert reply.status == 302
    assert reply.headers["location"] == "https://example.com/elsewhere"
    assert len(server.requests) == 1


def test_urllib_transport_returns_error_statuses(https: Callable[..., InMemoryHTTPS]) -> None:
    https((429, {"Retry-After": "120", "CF-Ray": "abc"}, b"slow down"))

    reply = probe.urllib_fetch(identity.BASE_URL + "/api/cities", {}, 5.0)

    assert reply == probe.Response(429, {"retry-after": "120", "cf-ray": "abc"}, b"slow down")


class Chunks:
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


@pytest.fixture
def small_limit(monkeypatch: pytest.MonkeyPatch) -> int:
    # read_body lives in recon/http_common.py (shared with the scanner) and reads its limit there.
    monkeypatch.setattr(http_common, "MAX_BODY_BYTES", 100)
    return 100


def test_body_up_to_the_limit_is_read_whole(small_limit: int) -> None:
    stream = Chunks(b"x" * 10, 10)

    assert probe.read_body(stream, None, stream.clock) == (b"x" * 100, None)


def test_body_over_the_limit_is_cut_and_refused(small_limit: int) -> None:
    stream = Chunks(b"x" * 10, 1000)

    body, problem = probe.read_body(stream, None, stream.clock)

    assert body == b"x" * 100
    assert problem is not None
    assert "D5" in problem
    assert stream.reads <= 11  # stops at the first byte over the limit


def test_declared_oversized_body_is_not_read(small_limit: int) -> None:
    stream = Chunks(b"x" * 10, 1000)

    body, problem = probe.read_body(stream, "101", stream.clock)

    assert (body, stream.reads) == (b"", 0)
    assert problem is not None
    assert "D5" in problem


@pytest.mark.parametrize("declared", ["30", " 30 ", "", "abc", "-5", "\u00b2", "\u0663\u0660"])
def test_declared_length_within_limit_or_unreadable_is_read(
    small_limit: int, declared: str
) -> None:
    stream = Chunks(b"x" * 10, 3)

    assert probe.read_body(stream, declared, stream.clock) == (b"x" * 30, None)


def test_eof_before_the_declared_length_is_a_truncated_body() -> None:
    stream = Chunks(b"x" * 10, 1)

    assert probe.read_body(stream, "100", stream.clock) == (
        b"x" * 10,
        "Odpowiedź ucięta: 10 z 100 B.",
    )


class SocketFromBytes:
    """Enough of a socket for http.client.HTTPResponse to parse ``data`` (no network)."""

    def __init__(self, data: bytes) -> None:
        self.data = data

    def makefile(self, mode: str) -> io.BytesIO:
        return io.BytesIO(self.data)


def http_response(raw: bytes) -> http.client.HTTPResponse:
    reply = http.client.HTTPResponse(SocketFromBytes(raw))  # type: ignore[arg-type]
    reply.begin()
    return reply


def test_real_http_response_closed_early_is_truncated_not_complete() -> None:
    """http.client's read1 reports a connection closed early as EOF, without an error."""
    reply = http_response(
        b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 100\r\n\r\n"
        b'{"a": [1, '
    )

    body, problem = probe.read_body(reply, reply.getheader("Content-Length"))

    assert body == b'{"a": [1, '
    assert problem == "Odpowiedź ucięta: 10 z 100 B."


def test_real_http_response_with_a_complete_body() -> None:
    reply = http_response(b'HTTP/1.1 200 OK\r\nContent-Length: 8\r\n\r\n{"a": 1}')

    assert probe.read_body(reply, reply.getheader("Content-Length")) == (b'{"a": 1}', None)


def test_read_from_a_closed_stream_is_a_problem() -> None:
    stream = Chunks(b"x", 2, then=ValueError("I/O operation on closed file."))

    body, problem = probe.read_body(stream, None, stream.clock)

    assert body == b"xx"
    assert problem is not None
    assert "closed file" in problem


def test_stream_without_read1_is_a_bug_that_propagates() -> None:
    with pytest.raises(AttributeError):
        probe.read_body(io.StringIO("x"), None)  # type: ignore[arg-type]


def test_slow_body_is_cut_at_the_deadline() -> None:
    stream = Chunks(b"x", 1000, tick=probe.BODY_DEADLINE / 4)

    body, problem = probe.read_body(stream, None, stream.clock)

    assert problem is not None
    assert f"{probe.BODY_DEADLINE:g} s" in problem
    # 4 reads fit in the deadline, the 5th crosses it, one more read checks for EOF.
    assert (body, stream.reads) == (b"x" * 6, 6)


def test_eof_right_after_the_deadline_is_a_complete_body() -> None:
    # The 2nd chunk arrives after the deadline, then the body ends.
    stream = Chunks(b"x", 2, tick=probe.BODY_DEADLINE * 0.75)

    assert probe.read_body(stream, None, stream.clock) == (b"xx", None)


@pytest.mark.parametrize(
    "error",
    [
        TimeoutError("timed out"),
        ConnectionResetError("reset"),
        http.client.IncompleteRead(b"ab", 10),
    ],
)
def test_read_error_keeps_what_was_read(error: Exception) -> None:
    stream = Chunks(b"x", 3, then=error)

    body, problem = probe.read_body(stream, None, stream.clock)

    assert body == b"xxx"
    assert problem is not None
    assert type(error).__name__ in problem


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


@pytest.mark.parametrize(
    ("status", "headers", "error", "code", "pause"),
    [
        (429, {"Retry-After": "120"}, TimeoutError("timed out"), STOP, 120.0),
        (429, {}, http.client.IncompleteRead(b"ab", 10), STOP, 60.0),
        (503, {"Retry-After": "45"}, ConnectionResetError("reset"), HTTP_ERROR, 45.0),
        (502, {}, TimeoutError("timed out"), HTTP_ERROR, 30.0),
    ],
)
def test_read_error_after_the_status_still_stops_and_pauses(
    env: Env,
    https: Callable[..., InMemoryHTTPS],
    capsys: pytest.CaptureFixture[str],
    status: int,
    headers: dict[str, str],
    error: Exception,
    code: int,
    pause: float,
) -> None:
    https((status, headers, FailingBody(b"partial", error)))

    result = probe.main(
        ["api", "/api/cities?q=krak"], limiter=env.limiter, samples_dir=env.samples_dir
    )

    assert result == code
    assert env.pause_after_last_request() == pytest.approx(pause)
    err = capsys.readouterr().err
    assert f"HTTP {status}" in err
    assert "Błąd sieci" not in err


def test_truncated_429_still_stops_and_pauses(
    env: Env, https: Callable[..., InMemoryHTTPS], capsys: pytest.CaptureFixture[str]
) -> None:
    https((429, {"Retry-After": "120", "Content-Length": "100"}, b"x" * 30))

    code = probe.main(
        ["api", "/api/cities?q=krak"], limiter=env.limiter, samples_dir=env.samples_dir
    )

    assert code == STOP
    assert env.pause_after_last_request() == pytest.approx(120)


@pytest.mark.parametrize(
    ("argv", "content_type", "body"),
    [
        (["api", "/api/cities?q=krak", "--save", "cut"], "application/json", b'{"a": [1, '),
        (
            ["page", "/ceny-ofertowe/x/mieszkania", "--prop", "initialData", "--save", "cut"],
            "text/x-component",
            b'2:["$","$L1",null,{"initialData":{"a":1},"rest":[1,2',  # the prop is complete
        ),
    ],
)
def test_truncated_200_fails_without_a_sample(
    env: Env,
    https: Callable[..., InMemoryHTTPS],
    capsys: pytest.CaptureFixture[str],
    argv: list[str],
    content_type: str,
    body: bytes,
) -> None:
    declared = str(len(body) + 100)
    https((200, {"Content-Type": content_type, "Content-Length": declared}, body))

    code = probe.main(argv, limiter=env.limiter, samples_dir=env.samples_dir)

    assert code == HTTP_ERROR
    captured = capsys.readouterr()
    assert f"ucięta: {len(body)} z {declared} B" in captured.err
    assert captured.out == ""
    assert list(env.samples_dir.iterdir()) == []


def test_429_with_a_non_ascii_digit_length_still_stops_and_pauses(
    env: Env, https: Callable[..., InMemoryHTTPS]
) -> None:
    # Headers are decoded as latin-1: the byte 0xB2 arrives as "²", which isdigit() accepts.
    https((429, {"Retry-After": "120", "Content-Length": "\u00b2"}, b"slow down"))

    code = probe.main(
        ["api", "/api/cities?q=krak"], limiter=env.limiter, samples_dir=env.samples_dir
    )

    assert code == STOP
    assert env.pause_after_last_request() == pytest.approx(120)


CHUNKED_JSON = b"10\r\n" + b'{"a": [1, 2, 3]}' + b"\r\n0\r\n\r\n"


@pytest.mark.parametrize("length", ["999", "101", "3"])
def test_chunked_body_ignores_content_length(
    env: Env,
    https: Callable[..., InMemoryHTTPS],
    capsys: pytest.CaptureFixture[str],
    small_limit: int,
    length: str,
) -> None:
    """999: no false truncation; 101 (over the limit of 100): no false refusal."""
    head = (
        f"Content-Type: application/json\r\nTransfer-Encoding: chunked\r\nContent-Length: {length}"
    )
    reply = http_response(f"HTTP/1.1 200 OK\r\n{head}\r\n\r\n".encode() + CHUNKED_JSON)
    headers = {"Content-Type": "application/json", "Transfer-Encoding": "chunked"}
    https((200, {**headers, "Content-Length": length}, reply))

    code = probe.main(
        ["api", "/api/cities?q=krak"], limiter=env.limiter, samples_dir=env.samples_dir
    )

    assert code == 0
    assert json.loads(capsys.readouterr().out) == {"a": [1, 2, 3]}


@pytest.mark.parametrize(
    ("status", "headers", "length"),
    [
        (200, {"Content-Length": "10"}, "10"),
        (200, {"Content-Length": "10", "Transfer-Encoding": "chunked"}, None),
        (101, {"Content-Length": "10"}, None),
        (204, {"Content-Length": "10"}, None),
        (304, {"Content-Length": "10"}, None),
        (404, {}, None),
    ],
)
def test_body_length_applies_only_where_it_describes_the_body(
    status: int, headers: dict[str, str], length: str | None
) -> None:
    lowered = {name.lower(): value for name, value in headers.items()}

    assert probe.body_length(status, lowered) == length


@pytest.mark.parametrize(("status", "code"), [(204, NO_DATA), (304, HTTP_ERROR)])
def test_no_body_statuses_are_not_reported_as_truncated(
    env: Env,
    https: Callable[..., InMemoryHTTPS],
    capsys: pytest.CaptureFixture[str],
    status: int,
    code: int,
) -> None:
    https((status, {"Content-Type": "application/json", "Content-Length": "50"}, b""))

    result = probe.main(
        ["api", "/api/cities?q=krak"], limiter=env.limiter, samples_dir=env.samples_dir
    )

    assert result == code
    err = capsys.readouterr().err
    assert f"HTTP {status}" in err
    assert "ucięta" not in err


def test_read_error_on_200_fails_without_a_sample(
    env: Env, https: Callable[..., InMemoryHTTPS], capsys: pytest.CaptureFixture[str]
) -> None:
    https((200, {"Content-Type": "application/json"}, FailingBody(b'{"a":', TimeoutError("x"))))

    code = probe.main(
        ["api", "/api/cities?q=krak", "--save", "cities"],
        limiter=env.limiter,
        samples_dir=env.samples_dir,
    )

    assert code == HTTP_ERROR
    assert "przerwane" in capsys.readouterr().err
    assert list(env.samples_dir.iterdir()) == []


def test_body_limits_are_the_agreed_ones() -> None:
    assert probe.MAX_BODY_BYTES == 32 * 1024 * 1024
    assert probe.BODY_DEADLINE == 120.0


def test_oversized_response_fails_through_the_urllib_transport(
    env: Env,
    https: Callable[..., InMemoryHTTPS],
    small_limit: int,
    capsys: pytest.CaptureFixture[str],
) -> None:
    https((200, {"Content-Type": "application/json"}, b"[" + b"1," * 100 + b"1]"))

    code = probe.main(
        ["api", "/api/map/powiat-sales/208", "--save", "dump"],
        limiter=env.limiter,
        samples_dir=env.samples_dir,
    )

    assert code == HTTP_ERROR
    assert "D5" in capsys.readouterr().err
    assert list(env.samples_dir.iterdir()) == []


def test_429_with_an_unread_body_still_stops_and_pauses(env: Env) -> None:
    reply = probe.Response(429, {"retry-after": "120"}, b"", "Odpowiedź przekracza limit")

    assert env.run(["api", "/api/cities?q=krak"], FakeService([reply])) == STOP
    assert env.pause_after_last_request() == pytest.approx(120)


# --- allowlist and input checks ------------------------------------------------------


@pytest.mark.parametrize(
    ("mode", "path", "hint"),
    [
        ("api", "https://" + HOST + "/api/cities", "pełny URL"),
        ("api", "http://" + HOST + "/api/cities", "pełny URL"),
        ("api", "https://example.com/api/cities", "pełny URL"),
        ("page", "https://" + HOST + "/ceny-ofertowe/warszawa/mieszkania", "pełny URL"),
        ("api", "//" + HOST + "/api/cities", "inny host"),
        ("api", "//example.com/api/cities", "inny host"),
        ("api", HOST + "/api/cities", "zaczynać się od /"),
        ("api", "api/cities", "zaczynać się od /"),
        ("api", "/api/unknown", "allowlist"),
        ("api", "/api/cities/extra", "allowlist"),
        ("api", "/api/valuation-pdf?investSlug=x&saleId=1&city=warszawa", "poza zakresem"),
        ("api", "/api/cities/../valuation-pdf", ".."),
        ("api", "/api/map/city-powiats/..", ".."),
        ("api", "/api//cities", "pust"),
        ("api", "/api/map/city-powiats/%2e%2e", "znaki"),
        ("api", "/api/map/city-powiats/a%2Fb", "znaki"),
        ("api", "/api/map/city-powiats/a\\b", "znaki"),
        ("api", "/api/cities?q=krak#top", "#"),
        ("api", "/api/cities?q=a\r\nX-Injected: 1", "znaki"),
        ("api", "/ceny-ofertowe/warszawa/mieszkania", "page"),
        ("page", "/api/cities", "api"),
        ("page", "/wycena", "allowlist"),
        ("page", "/zglos-dewelopera", "allowlist"),
        ("page", "/ceny-ofertowe/warszawa/mieszkania?_rsc=abc", "_rsc"),
        ("page", "/ceny-ofertowe/warszawa/mieszkania?page=2&_rsc", "_rsc"),
        ("page", "/ceny-ofertowe/warszawa/mieszkania?%5Frsc=abc", "_rsc"),
        ("page", "/ceny-ofertowe/warszawa/mieszkania?%5frsc=abc", "_rsc"),
        ("page", "/ceny-ofertowe/warszawa/mieszkania?_rsc%3D1", "_rsc"),
    ],
)
def test_rejected_paths_send_nothing(
    env: Env, capsys: pytest.CaptureFixture[str], mode: str, path: str, hint: str
) -> None:
    service = FakeService([])

    code = env.run([mode, path], service)

    assert code == USAGE
    assert service.requests == []
    assert hint in capsys.readouterr().err


def exit_code(run: Callable[[], int]) -> int | str | None:
    """Exit code of a run, also when argparse rejects the options with SystemExit."""
    try:
        return run()
    except SystemExit as exc:
        return exc.code


@pytest.mark.parametrize(
    "argv",
    [
        ["api", "/api/cities", "--max-wait", "nan"],
        ["api", "/api/cities", "--max-wait", "-1"],
        ["api", "/api/cities", "--max-wait=-1"],
        ["api", "/api/cities", "--max-wait", "inf"],
        ["api", "/api/cities", "--max-wait", "abc"],
        ["api", "/api/cities", "--trim", "-1"],
        ["api", "/api/cities", "--trim", "1.5"],
        ["api", "/api/cities", "--prop", "initialData"],  # page only
        ["page", "/ceny-ofertowe/warszawa/mieszkania", "--prop", "a-b"],
        ["page", "/ceny-ofertowe/warszawa/mieszkania", "--prop", 'x"'],
        ["page", "/ceny-ofertowe/warszawa/mieszkania", "--prop", ""],
        ["page", "/ceny-ofertowe/warszawa/mieszkania", "--prop", "1abc"],
    ],
)
def test_bad_options_send_nothing(env: Env, argv: list[str]) -> None:
    service = FakeService([])

    assert exit_code(lambda: env.run(argv, service)) == USAGE
    assert service.requests == []


# --- limiter -------------------------------------------------------------------------


def lock_is_held(lock_path: Path) -> bool:
    fd = os.open(lock_path, os.O_RDWR)  # a separate open file description
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return True
    else:
        fcntl.flock(fd, fcntl.LOCK_UN)
        return False
    finally:
        os.close(fd)


def test_request_runs_inside_the_limiter_slot(env: Env) -> None:
    held: list[bool] = []
    service = FakeService(
        [json_response({})],
        on_request=lambda: held.append(lock_is_held(env.lock_dir / LOCK_FILENAME)),
    )

    env.run(["api", "/api/popular-search-items"], service)

    assert held == [True]
    assert not lock_is_held(env.lock_dir / LOCK_FILENAME)
    state = json.loads((env.lock_dir / LOCK_FILENAME).read_text())
    assert set(state) == {"last_end", "next_start"}


def test_wait_too_long_sends_nothing(env: Env, capsys: pytest.CaptureFixture[str]) -> None:
    with env.limiter.slot() as slot:
        slot.defer(600)
    service = FakeService([])

    code = env.run(["api", "/api/popular-search-items", "--max-wait", "5"], service)

    assert code == WAIT
    assert service.requests == []
    err = capsys.readouterr().err
    assert "600 s" in err
    assert "nie wysłał" in err


# --- stop: 401, 403, 429, challenge ---------------------------------------------------


@pytest.mark.parametrize("status", [401, 403, 429])
def test_blocking_statuses_stop_without_retry(
    env: Env, capsys: pytest.CaptureFixture[str], status: int
) -> None:
    service = FakeService([json_response({"error": "x"}, status), json_response({})])

    code = env.run(["api", "/api/cities?q=krak"], service)

    assert code == STOP
    assert len(service.requests) == 1
    err = capsys.readouterr().err
    assert f"HTTP {status}" in err
    assert "Przerwij serię" in err


def test_429_retry_after_seconds_is_recorded_in_the_limiter(
    env: Env, capsys: pytest.CaptureFixture[str]
) -> None:
    service = FakeService([response(429, b"", "text/plain", retry_after="120")])

    code = env.run(["api", "/api/cities?q=krak"], service)

    assert code == STOP
    assert env.pause_after_last_request() == pytest.approx(120)
    assert "120 s" in capsys.readouterr().err


def test_429_retry_after_date_is_recorded_in_the_limiter(env: Env) -> None:
    service = FakeService([response(429, retry_after=formatdate(NOW + 90, usegmt=True))])

    code = env.run(["api", "/api/cities?q=krak"], service, clock=lambda: NOW)

    assert code == STOP
    assert env.pause_after_last_request() == pytest.approx(90)


def test_429_retry_after_beyond_the_cap_still_pauses(
    env: Env, capsys: pytest.CaptureFixture[str]
) -> None:
    service = FakeService([response(429, retry_after="99999")])

    code = env.run(["api", "/api/cities?q=krak"], service)

    assert code == STOP
    assert env.pause_after_last_request() == pytest.approx(MAX_DEFER)
    assert "3600" in capsys.readouterr().err


def test_429_retry_after_overflowing_digits_pause_the_cap(env: Env) -> None:
    service = FakeService([response(429, retry_after="9" * 400)])

    assert env.run(["api", "/api/cities?q=krak"], service) == STOP
    assert env.pause_after_last_request() == pytest.approx(MAX_DEFER)


@pytest.mark.parametrize(
    "reply",
    [
        response(429),
        response(429, retry_after="soon"),
        response(429, retry_after="0"),
        response(429, retry_after="5"),
        response(429, retry_after=formatdate(NOW - 600, usegmt=True)),
        response(429, CHALLENGE_HTML, "text/html", cf_mitigated="challenge"),
    ],
)
def test_429_pauses_the_limiter_at_least_a_minute(
    env: Env, capsys: pytest.CaptureFixture[str], reply: probe.Response
) -> None:
    service = FakeService([reply])

    code = env.run(["api", "/api/cities?q=krak"], service, clock=lambda: NOW)

    assert code == STOP
    assert env.pause_after_last_request() == pytest.approx(probe.PAUSE_AFTER_429)
    assert "60 s" in capsys.readouterr().err


def test_pause_after_429_is_a_minute() -> None:
    assert probe.PAUSE_AFTER_429 == 60.0


@pytest.mark.parametrize(
    "reply",
    [
        json_response({}, 200, cf_mitigated="challenge"),
        response(403, CHALLENGE_HTML, "text/html", cf_mitigated="challenge"),
        response(200, CHALLENGE_HTML, "text/html; charset=UTF-8"),
        response(200, CHALLENGE_HTML),  # HTML without a content type
    ],
)
def test_cloudflare_challenge_stops_api(
    env: Env, capsys: pytest.CaptureFixture[str], reply: probe.Response
) -> None:
    service = FakeService([reply, json_response({})])

    code = env.run(["api", "/api/cities?q=krak"], service)

    assert code == STOP
    assert len(service.requests) == 1
    err = capsys.readouterr().err
    assert "Przerwij serię" in err
    # The STOP names a status only when it is a STOP status itself (http_policy): a
    # "HTTP 200" there reads like success; the status line above still shows it.
    stop_line = next(line for line in err.splitlines() if line.startswith("STOP: "))
    expected = "HTTP 403 (odmowa dostępu), " if reply.status == 403 else ""
    assert stop_line.startswith(f"STOP: {expected}challenge Cloudflare (captcha/WAF). ")


def test_challenge_on_503_stops_and_records_retry_after(env: Env) -> None:
    service = FakeService([response(503, CHALLENGE_HTML, "text/html", retry_after="45")])

    code = env.run(["page", "/ceny-ofertowe/warszawa/mieszkania", "--prop", "x"], service)

    assert code == STOP
    assert env.pause_after_last_request() == pytest.approx(45)


def test_challenge_html_instead_of_rsc_stops_page(env: Env) -> None:
    service = FakeService([response(200, CHALLENGE_HTML, "text/html")])

    assert env.run(["page", "/ceny-ofertowe/warszawa/mieszkania"], service) == STOP


@pytest.mark.parametrize(
    "marker",
    [
        "window._cf_chl_opt={}",
        '<div id="cf-browser-verification">',
        '<input name="cf_captcha_kind" value="h">',
        "<title>Just a moment...</title>",
        "<title>Attention Required! | Cloudflare</title>",
    ],
)
def test_each_challenge_marker_stops(env: Env, marker: str) -> None:
    html = f"<!DOCTYPE html><html><head></head><body>{marker}</body></html>"
    service = FakeService([response(200, html.encode(), "text/html")])

    assert env.run(["api", "/api/cities?q=krak"], service) == STOP


def test_app_html_with_turnstile_is_not_a_challenge(
    env: Env, capsys: pytest.CaptureFixture[str]
) -> None:
    row = rsc_text({"developerAbuseData": [{"developer_abuse_id": 11}]})
    html = (
        "<!DOCTYPE html><html><head><title>Mapa zgłoszeń</title>"
        '<script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async></script>'
        '<script src="/cdn-cgi/challenge-platform/scripts/jsd/main.js"></script></head><body>'
        f"<script>self.__next_f.push([1,{json.dumps(row)}])</script></body></html>"
    )
    service = FakeService([response(200, html.encode(), "text/html; charset=utf-8")])

    code = env.run(
        ["page", "/zglos-dewelopera/mapa-zgloszen", "--prop", "developerAbuseData"], service
    )

    assert code == 0
    assert json.loads(capsys.readouterr().out) == [{"developer_abuse_id": 11}]


def test_turnstile_mention_inside_rsc_is_not_a_challenge(
    env: Env, capsys: pytest.CaptureFixture[str]
) -> None:
    props = {"initialData": {"a": 1}, "script": "https://challenges.cloudflare.com/turnstile"}
    service = FakeService([rsc_response(props)])

    code = env.run(["page", "/zglos-dewelopera/mapa-zgloszen", "--prop", "initialData"], service)

    assert code == 0
    assert json.loads(capsys.readouterr().out) == {"a": 1}


# --- the STOP record (every process) ---------------------------------------------------


@pytest.mark.parametrize(
    ("reply", "status", "reason"),
    [
        (json_response({"error": "x"}, 401), 401, "brak autoryzacji"),
        (json_response({"error": "x"}, 403), 403, "odmowa dostępu"),
        (response(429, retry_after="90"), 429, "limit zapytań"),
        (
            response(200, CHALLENGE_HTML, "text/html"),
            "challenge",
            "challenge Cloudflare (captcha/WAF)",
        ),
    ],
    ids=["401", "403", "429", "challenge"],
)
def test_a_stop_is_recorded_and_ends_the_next_run_before_it_sends(
    env: Env,
    capsys: pytest.CaptureFixture[str],
    reply: probe.Response,
    status: int | str,
    reason: str,
) -> None:
    service = FakeService([reply, json_response({})])

    assert env.run(["api", "/api/cities?q=krak"], service) == STOP
    state = env.limiter.stop_status()
    assert isinstance(state.stop, StopRecord)
    assert (state.stop.status, state.stop.reason, state.stop.source) == (status, reason, "probe")
    assert (state.stop.until is not None) is (status == 429)
    first = capsys.readouterr().err
    # recon-verifier is a model too: nothing about when it ends or how to lift it.
    assert "Zapisano STOP: inne procesy też zostały wstrzymane.\n" in first
    assert "/api/" not in (env.lock_dir / STOP_FILENAME).read_text(encoding="utf-8")

    assert env.run(["api", "/api/popular-search-items", "--max-wait", "5"], service) == STOP

    assert len(service.requests) == 1
    second = capsys.readouterr().err
    assert second.startswith("STOP: seria zapytań do deweloperuch.pl jest wstrzymana")
    assert reason.split(" (")[0] in second and "probe" not in second
    assert second.endswith("zgłoś to użytkownikowi.\n")


@pytest.mark.parametrize("source", ["pakiet", "scan_bundles"])
def test_a_stop_recorded_by_another_program_ends_the_run(
    env: Env, capsys: pytest.CaptureFixture[str], source: str
) -> None:
    with env.limiter.slot() as slot:
        slot.stop(403, "odmowa dostępu", source=source)
    service = FakeService([json_response({})])

    code = env.run(["api", "/api/cities?q=krak"], service)

    assert code == STOP
    assert service.requests == []
    err = capsys.readouterr().err
    assert "wcześniejszym STOP" in err and "odmowa dostępu" in err
    assert source not in err  # the program is a detail for people (stop status)


def test_an_unreadable_record_ends_the_run(env: Env, capsys: pytest.CaptureFixture[str]) -> None:
    env.lock_dir.mkdir()
    (env.lock_dir / STOP_FILENAME).write_text("{", encoding="utf-8")
    service = FakeService([json_response({})])

    assert env.run(["api", "/api/cities?q=krak"], service) == STOP
    assert service.requests == []
    assert "nieczytelny" in capsys.readouterr().err


def test_usage_errors_come_before_the_stop(env: Env) -> None:
    with env.limiter.slot() as slot:
        slot.stop(403, "odmowa dostępu", source="pakiet")

    assert env.run(["api", "/api/not-documented"], FakeService([])) == USAGE


def test_the_stop_is_recorded_before_the_lock_is_released(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen_at_unlock: list[bool] = []
    real_flock = fcntl.flock

    def flock(fd: int, operation: int) -> None:
        if operation == fcntl.LOCK_UN:
            seen_at_unlock.append((env.lock_dir / STOP_FILENAME).exists())
        real_flock(fd, operation)

    monkeypatch.setattr(fcntl, "flock", flock)

    assert env.run(["api", "/api/cities?q=krak"], FakeService([response(403)])) == STOP
    assert seen_at_unlock == [True]


def test_a_stop_that_cannot_be_recorded_is_still_a_stop(
    env: Env, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def disk_full(*args: object, **kwargs: object) -> None:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(Slot, "stop", disk_full)

    assert env.run(["api", "/api/cities?q=krak"], FakeService([response(403)])) == STOP
    assert "Uwaga: STOP nie został zapisany dla innych procesów" in capsys.readouterr().err
    assert not (env.lock_dir / STOP_FILENAME).exists()


# --- other HTTP outcomes ---------------------------------------------------------------


def test_503_records_retry_after_and_fails(env: Env, capsys: pytest.CaptureFixture[str]) -> None:
    service = FakeService([response(503, b"maintenance", "text/plain", retry_after="45")])

    code = env.run(["api", "/api/cities?q=krak"], service)

    assert code == HTTP_ERROR
    assert len(service.requests) == 1
    assert env.pause_after_last_request() == pytest.approx(45)
    err = capsys.readouterr().err
    assert "maintenance" in err
    assert "45 s" in err


@pytest.mark.parametrize(
    ("reply", "pause"),
    [
        (response(502), probe.PAUSE_AFTER_5XX),
        (response(503, retry_after="soon"), probe.PAUSE_AFTER_5XX),
        (response(504, retry_after="-5"), probe.PAUSE_AFTER_5XX),
        (response(504, retry_after="120"), 120.0),
        (response(503, retry_after="0"), 0.0),  # the service allows a retry now
    ],
)
def test_gateway_errors_pause_the_limiter(env: Env, reply: probe.Response, pause: float) -> None:
    assert env.run(["api", "/api/cities?q=krak"], FakeService([reply])) == HTTP_ERROR
    assert env.pause_after_last_request() == pytest.approx(pause, abs=0.01)


def test_pause_after_gateway_errors_is_half_a_minute() -> None:
    assert probe.PAUSE_AFTER_5XX == 30.0


@pytest.mark.parametrize("status", [500, 501, 505])
def test_other_5xx_fail_without_pause(env: Env, status: int) -> None:
    service = FakeService([response(status, b"oops", retry_after="30")])

    assert env.run(["api", "/api/cities?q=krak"], service) == HTTP_ERROR
    assert env.pause_after_last_request() == pytest.approx(0, abs=0.01)


def test_client_error_shows_the_body(env: Env, capsys: pytest.CaptureFixture[str]) -> None:
    service = FakeService([json_response({"error": "Valid investRcnId is required"}, 400)])

    code = env.run(["api", "/api/avg-price-trend/building/slug"], service)

    assert code == HTTP_ERROR
    assert "Valid investRcnId is required" in capsys.readouterr().err


def test_redirect_is_reported_not_followed(env: Env, capsys: pytest.CaptureFixture[str]) -> None:
    service = FakeService([response(308, location="/ceny-ofertowe/warszawa/mieszkania/")])

    code = env.run(["page", "/ceny-ofertowe/warszawa/mieszkania"], service)

    assert code == HTTP_ERROR
    assert len(service.requests) == 1
    assert "/ceny-ofertowe/warszawa/mieszkania/" in capsys.readouterr().err


@pytest.mark.parametrize(
    "error", [urllib.error.URLError("connection refused"), TimeoutError("timed out")]
)
def test_network_error(env: Env, error: Exception) -> None:
    def failing(url: str, headers: Mapping[str, str], timeout: float) -> probe.Response:
        raise error

    assert env.run(["api", "/api/cities?q=krak"], failing) == HTTP_ERROR


# --- response content -----------------------------------------------------------------


@pytest.mark.parametrize(
    "reply",
    [
        response(200, b"not json", "application/json"),
        response(200, b"<!DOCTYPE html><html><body>page</body></html>", "text/html"),
    ],
)
def test_api_without_json_fails(env: Env, reply: probe.Response) -> None:
    assert env.run(["api", "/api/cities?q=krak"], FakeService([reply])) == NO_DATA


def test_page_prop_takes_the_first_hit(env: Env, capsys: pytest.CaptureFixture[str]) -> None:
    second = '3:["$","$L1",null,{"initialData":{"page":2}}]\n'
    text = rsc_text({"initialData": {"page": 1}}) + second
    service = FakeService([response(200, text.encode(), "text/x-component")])

    code = env.run(["page", "/ceny-ofertowe/warszawa/mieszkania", "--prop", "initialData"], service)

    assert code == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {"page": 1}
    assert "2 razy" in captured.err


def test_page_missing_prop_lists_what_is_there(
    env: Env, capsys: pytest.CaptureFixture[str]
) -> None:
    service = FakeService([rsc_response({"initialData": {}, "serverPaginationData": {}})])

    code = env.run(["page", "/ceny-ofertowe/warszawa/inwestycje", "--prop", "investments"], service)

    assert code == NO_DATA
    err = capsys.readouterr().err
    assert "investments" in err
    assert "initialData" in err
    assert "serverPaginationData" in err


def test_page_without_prop_lists_data_props(env: Env, capsys: pytest.CaptureFixture[str]) -> None:
    props = {
        "investments": [{"invest_id": i} for i in range(50)],
        "serverPaginationData": {"currentPage": 1, "perPage": 50},
        "initialSortBy": "avg_price_sqm",
        "includeArchived": False,
    }
    service = FakeService([rsc_response(props)])

    code = env.run(["page", "/ceny-ofertowe/warszawa/inwestycje"], service)

    assert code == 0
    assert json.loads(capsys.readouterr().out) == [
        {"name": "investments", "type": "array", "size": 50},
        {"name": "serverPaginationData", "type": "object", "size": 2},
    ]


def test_page_without_prop_lists_the_data_of_the_real_offers_page(
    env: Env, capsys: pytest.CaptureFixture[str]
) -> None:
    """The real page: the data row follows text rows without a newline; the list still
    shows it (before 2026-10-10 it stopped at the layout's props)."""
    service = FakeService([response(200, raw(OFFERS_WARSZAWA), "text/x-component")])

    code = env.run(["page", "/ceny-ofertowe/warszawa/mieszkania?perPage=10"], service)

    assert code == 0
    listed = json.loads(capsys.readouterr().out)
    assert {"name": "initialData", "type": "object", "size": 2} in listed
    assert {"name": "initialApiParams", "type": "object", "size": 17} in listed


def test_page_prop_of_the_real_offers_page(env: Env, capsys: pytest.CaptureFixture[str]) -> None:
    service = FakeService([response(200, raw(OFFERS_WARSZAWA), "text/x-component")])

    code = env.run(
        ["page", "/ceny-ofertowe/warszawa/mieszkania?perPage=10", "--prop", "initialData"],
        service,
    )

    assert code == 0
    value = json.loads(capsys.readouterr().out)
    assert value["pagination"] == {"page": 1, "perPage": 10, "total": 13324, "totalPages": 20}


def test_page_prop_missing_on_the_real_unknown_city_page(
    env: Env, capsys: pytest.CaptureFixture[str]
) -> None:
    service = FakeService([response(200, raw(OFFERS_UNKNOWN_CITY), "text/x-component")])

    code = env.run(
        ["page", "/ceny-ofertowe/nieistniejace-miasto/mieszkania", "--prop", "initialData"],
        service,
    )

    assert code == NO_DATA
    err = capsys.readouterr().err
    assert "Nie znaleziono propsa 'initialData'" in err
    assert "segmentPath" in err


def test_page_served_as_html_is_decoded_with_a_warning(
    env: Env, capsys: pytest.CaptureFixture[str]
) -> None:
    row = rsc_text({"initialData": {"a": 1}})
    html = f"<html><body><script>self.__next_f.push([1,{json.dumps(row)}])</script></body></html>"
    service = FakeService([response(200, html.encode(), "text/html; charset=utf-8")])

    code = env.run(["page", "/ceny-ofertowe/warszawa/mieszkania", "--prop", "initialData"], service)

    assert code == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out) == {"a": 1}
    assert "HTML" in captured.err


def test_stdout_trim_applies_to_lists_and_maps_follow_the_sample_rule(
    env: Env, capsys: pytest.CaptureFixture[str]
) -> None:
    data = {
        "data": list(range(10)),
        "byId": {str(i): i for i in range(10)},
        "big": {str(i): [i] for i in range(41)},
    }
    service = FakeService([json_response(data)] * 3)

    env.run(["api", "/api/monthly-transaction-stats?citySlug=warszawa"], service)
    default = json.loads(capsys.readouterr().out)
    env.run(["api", "/api/monthly-transaction-stats?citySlug=warszawa", "--trim", "1"], service)
    one = json.loads(capsys.readouterr().out)
    env.run(["api", "/api/monthly-transaction-stats?citySlug=warszawa", "--full"], service)
    full = json.loads(capsys.readouterr().out)

    assert default["data"] == [0, 1, 2, "... (7 more, 10 total)"]
    assert default["byId"] == data["byId"]
    assert default["big"] == {"0": [0], "1": [1], "...": "39 more keys"}
    assert one["data"] == [0, "... (9 more, 10 total)"]
    assert one["byId"] == data["byId"]
    assert one["big"] == default["big"]
    assert full == data


def test_trim_and_full_are_exclusive(env: Env) -> None:
    with pytest.raises(SystemExit) as exc:
        env.run(["api", "/api/cities", "--trim", "2", "--full"], FakeService([]))

    assert exc.value.code == USAGE


# --- --save ---------------------------------------------------------------------------

# Every api sample without personal data is reproduced byte for byte; the one with
# personal data is checked in test_save_redacts_free_text_in_rcn_records.
API_SAMPLES = sorted(
    path.name for path in SAMPLES.glob("api.*.json") if path.name != "api.tx_visible.json"
)
PAGE_PROP_SAMPLES = [
    "page.offers_list.json",
    "page.offers_list.filtered.json",
    "page.transactions_list.json",
]


def test_sample_lists_are_not_empty() -> None:
    assert len(API_SAMPLES) >= 30
    assert "api.inv_sale_events.json" in API_SAMPLES  # id-keyed map below the threshold


@pytest.mark.parametrize("name", API_SAMPLES)
def test_save_api_reproduces_existing_sample(env: Env, name: str) -> None:
    sample = load_sample(name)
    path = sample["_request"].removeprefix("GET ")
    service = FakeService([json_response(untrim(sample["response"]))])
    save_as = name.removeprefix("api.").removesuffix(".json")
    captured = date.fromisoformat(sample["_captured"])  # samples come from different days

    code = env.run(["api", path, "--save", save_as], service, today=captured)

    assert code == 0
    written = (env.samples_dir / name).read_text(encoding="utf-8")
    assert written == (SAMPLES / name).read_text(encoding="utf-8")


@pytest.mark.parametrize("name", PAGE_PROP_SAMPLES)
def test_save_page_prop_reproduces_existing_sample(env: Env, name: str) -> None:
    sample = load_sample(name)
    path = sample["_request"].removeprefix("GET ").removesuffix(" (RSC)")
    prop = sample["_prop"]
    service = FakeService([rsc_response({prop: untrim(sample["value"]), "other": [1, 2]})])
    save_as = name.removeprefix("page.").removesuffix(".json")

    code = env.run(["page", path, "--prop", prop, "--save", save_as], service)

    assert code == 0
    written = (env.samples_dir / name).read_text(encoding="utf-8")
    assert written == (SAMPLES / name).read_text(encoding="utf-8")


def test_save_full_stdout_keeps_sample_trimmed(
    env: Env, capsys: pytest.CaptureFixture[str]
) -> None:
    service = FakeService([json_response({"data": list(range(10))})])

    env.run(["api", "/api/announcement-stats?region=x", "--full", "--save", "ann.full"], service)

    assert json.loads(capsys.readouterr().out) == {"data": list(range(10))}
    saved = json.loads((env.samples_dir / "api.ann.full.json").read_text(encoding="utf-8"))
    assert saved == {
        "_request": "GET /api/announcement-stats?region=x",
        "_captured": "2026-10-09",
        "response": {"data": [0, 1, 2, "... (7 more, 10 total)"]},
    }


def test_save_keeps_id_keyed_maps_up_to_the_threshold(env: Env) -> None:
    data = {str(2000 + i): [{"amount": i}] * 5 for i in range(probe.SAMPLE_MAP_THRESHOLD)}
    service = FakeService([json_response(data)])

    env.run(["api", "/api/investments/33/sale-events", "--save", "events"], service)

    saved = json.loads((env.samples_dir / "api.events.json").read_text("utf-8"))
    assert list(saved["response"]) == list(data)
    assert saved["response"]["2000"] == [{"amount": 0}] * 3 + ["... (2 more, 5 total)"]


def test_save_trims_id_keyed_maps_above_the_threshold(env: Env) -> None:
    data = {str(2000 + i): [{"amount": i}] * 5 for i in range(probe.SAMPLE_MAP_THRESHOLD + 1)}
    service = FakeService([json_response(data)])

    env.run(["api", "/api/investments/33/sale-events", "--save", "events"], service)

    saved = json.loads((env.samples_dir / "api.events.json").read_text("utf-8"))
    tail = ["... (2 more, 5 total)"]
    assert saved["response"] == {
        "2000": [{"amount": 0}] * 3 + tail,
        "2001": [{"amount": 1}] * 3 + tail,
        "...": "39 more keys",
    }


def test_map_threshold_matches_the_samples() -> None:
    assert (probe.SAMPLE_MAP_THRESHOLD, probe.SAMPLE_KEYS) == (40, 2)


@pytest.mark.parametrize(
    "data",
    [
        {**{str(i): [] for i in range(50)}, "a": []},  # not only numeric keys
        {f"{i}.5": [] for i in range(50)},  # not plain ids
        {f"-{i}": [] for i in range(50)},
    ],
)
def test_save_keeps_other_maps(env: Env, data: dict[str, Any]) -> None:
    service = FakeService([json_response(data)])

    env.run(["api", "/api/sale-events-rcn/batch?ids=1", "--save", "batch"], service)

    saved = json.loads((env.samples_dir / "api.batch.json").read_text("utf-8"))
    assert saved["response"] == data


def redact_by_hand(value: Any, key: str) -> Any:
    if isinstance(value, dict):
        return {
            k: ("[usunięte]" if k == key and v not in (None, "") else redact_by_hand(v, key))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [redact_by_hand(item, key) for item in value]
    return value


def test_save_redacts_free_text_in_rcn_records(env: Env) -> None:
    sample = load_sample("api.tx_visible.json")
    path = sample["_request"].removeprefix("GET ")
    service = FakeService([json_response(untrim(sample["response"]))])

    env.run(["api", path, "--save", "tx_visible"], service)

    saved = json.loads((env.samples_dir / "api.tx_visible.json").read_text("utf-8"))
    assert saved == redact_by_hand(sample, "additionalInfo")
    assert "[usunięte]" in json.dumps(saved, ensure_ascii=False)


def test_save_redacts_reports_on_the_abuse_map(env: Env) -> None:
    data = untrim(load_sample("page.developer_abuse_map.json")["props"]["developerAbuseData"])
    service = FakeService([rsc_response({"developerAbuseData": data})])

    env.run(
        ["page", "/zglos-dewelopera/mapa-zgloszen", "--prop", "developerAbuseData", "--save", "x"],
        service,
    )

    saved = json.loads((env.samples_dir / "page.x.json").read_text("utf-8"))
    assert saved["_request"] == "GET /zglos-dewelopera/mapa-zgloszen (RSC)"
    assert saved["_prop"] == "developerAbuseData"
    assert [item["additionalInfo"] for item in saved["value"][:3]] == ["[usunięte]"] * 3
    assert saved["value"][3] == "... (102 more, 105 total)"


def test_personal_data_is_redacted_at_every_level_also_on_stdout(
    env: Env, capsys: pytest.CaptureFixture[str]
) -> None:
    data = {
        "email": "jan@example.com",
        "Phone": "+48 600 000 000",
        "contact": {"telefon": "600000000", "e-mail": "a@b.pl", "name": "Biuro"},
        "items": [{"phone": 600000000, "additionalInfo": "Jan Kowalski, tel. 600"}],
        "additionalInfo": None,
        "telephone": "",
    }
    service = FakeService([json_response(data)])

    env.run(["api", "/api/developers?q=atal", "--save", "devs"], service)

    expected = {
        "email": "[usunięte]",
        "Phone": "[usunięte]",
        "contact": {"telefon": "[usunięte]", "e-mail": "[usunięte]", "name": "Biuro"},
        "items": [{"phone": "[usunięte]", "additionalInfo": "[usunięte]"}],
        "additionalInfo": None,
        "telephone": "",
    }
    assert json.loads(capsys.readouterr().out) == expected
    saved = json.loads((env.samples_dir / "api.devs.json").read_text("utf-8"))
    assert saved["response"] == expected


def test_save_never_overwrites(env: Env, capsys: pytest.CaptureFixture[str]) -> None:
    existing = env.samples_dir / "api.city_lookup.json"
    existing.write_text("original", encoding="utf-8")
    service = FakeService([json_response({})])

    code = env.run(["api", "/api/city-lookup?city=x", "--save", "city_lookup"], service)

    assert code == USAGE
    assert service.requests == []
    assert existing.read_text(encoding="utf-8") == "original"
    assert "city_lookup.v2" in capsys.readouterr().err


def test_save_never_overwrites_a_file_created_meanwhile(env: Env) -> None:
    target = env.samples_dir / "api.city_lookup.json"
    service = FakeService(
        [json_response({"city": "X"})],
        on_request=lambda: target.write_text("raced", encoding="utf-8"),
    )

    code = env.run(["api", "/api/city-lookup?city=x", "--save", "city_lookup"], service)

    assert code == USAGE
    assert target.read_text(encoding="utf-8") == "raced"


def test_save_prefix_follows_mode_and_variant(env: Env) -> None:
    service = FakeService([json_response({}), rsc_response({"initialData": {}})])

    env.run(["api", "/api/city-lookup?city=x", "--save", "lookup.v2"], service)
    env.run(
        ["page", "/ceny-ofertowe/x/mieszkania", "--prop", "initialData", "--save", "lookup.v2"],
        service,
    )

    assert sorted(p.name for p in env.samples_dir.iterdir()) == [
        "api.lookup.v2.json",
        "page.lookup.v2.json",
    ]


@pytest.mark.parametrize(
    "name",
    ["", "../x", "x/../../y", "a/b", "X", "a.b.c", ".a", "a.", "a b", "ą", "a-b", "x.json/"],
)
def test_save_rejects_bad_names(env: Env, name: str) -> None:
    service = FakeService([json_response({})])

    code = env.run(["api", "/api/city-lookup?city=x", "--save", name], service)

    assert code == USAGE
    assert service.requests == []
    assert list(env.samples_dir.iterdir()) == []


def test_save_page_needs_prop(env: Env) -> None:
    service = FakeService([rsc_response({})])

    code = env.run(["page", "/ceny-ofertowe/x/mieszkania", "--save", "x"], service)

    assert code == USAGE
    assert service.requests == []


def test_save_needs_the_samples_directory(env: Env, tmp_path: Path) -> None:
    service = FakeService([json_response({})])

    code = probe.main(
        ["api", "/api/cities", "--save", "x"],
        fetch=service,
        limiter=env.limiter,
        samples_dir=tmp_path / "missing",
    )

    assert code == USAGE
    assert service.requests == []


def test_save_reports_a_file_that_cannot_be_created(
    env: Env, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def no_permission(*args: Any, **kwargs: Any) -> Any:
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(probe, "open", no_permission, raising=False)

    code = env.run(["api", "/api/cities", "--save", "cities"], FakeService([json_response({})]))

    assert code == USAGE
    assert "Permission denied" in capsys.readouterr().err


def test_save_removes_its_own_partial_file(
    env: Env, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class DiskFull(io.StringIO):
        def write(self, text: str) -> int:
            raise OSError(28, "No space left on device")

    created: list[Path] = []

    def open_full(file: Path, mode: str, encoding: str) -> DiskFull:
        Path(file).touch(exist_ok=False)  # "x" mode: the run creates the file
        created.append(Path(file))
        return DiskFull()

    monkeypatch.setattr(probe, "open", open_full, raising=False)

    code = env.run(["api", "/api/cities", "--save", "cities"], FakeService([json_response({})]))

    assert code == USAGE
    assert created == [env.samples_dir / "api.cities.json"]
    assert list(env.samples_dir.iterdir()) == []
    assert "No space left" in capsys.readouterr().err


@pytest.mark.parametrize("depth", [100_000, 3_000])
def test_too_deeply_nested_json_fails_cleanly(
    env: Env, capsys: pytest.CaptureFixture[str], depth: int
) -> None:
    """100 000 levels stop the JSON decoder; 3 000 parse but exceed the Python stack."""
    body = b"[" * depth + b"]" * depth
    service = FakeService([response(200, body, "application/json")])

    code = env.run(["api", "/api/cities", "--save", "deep"], service)

    assert code == NO_DATA
    assert "zbyt głęboko" in capsys.readouterr().err
    assert list(env.samples_dir.iterdir()) == []


@pytest.mark.parametrize(
    ("mode", "path", "prop"),
    [
        ("api", "/api/map/powiat-sales/208", None),
        ("page", "/statystyki/ceny-transakcyjne/mieszkania/warszawa", "rawTransactions"),
    ],
)
def test_probe_may_still_read_what_the_package_client_treats_as_a_dump(
    tmp_path: Path, mode: str, path: str, prop: str | None
) -> None:
    """DUMP_PATHS bind the package's client only; probe keeps its allowlist (D5 via body limit)."""
    plan = probe.make_plan(mode, path, prop, None, tmp_path)

    assert plan.url.startswith(identity.BASE_URL + path)


def test_default_samples_dir_is_the_repo_one() -> None:
    assert probe.SAMPLES_DIR == SAMPLES


# --- running as a script ----------------------------------------------------------------


def run_script(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    # -S: no site-packages, so probe and everything it imports must be stdlib or repo code.
    return subprocess.run(
        [sys.executable, "-E", "-s", "-S", str(PROBE), *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=30,
        check=False,
    )


def test_help_works_offline_without_installed_packages(tmp_path: Path) -> None:
    result = run_script("--help", cwd=tmp_path)

    assert result.returncode == 0, result.stderr
    for text in ("api", "page", "kody wyjścia", "STOP"):
        assert text in result.stdout
    for code in range(2, 7):
        assert re.search(rf"^\s+{code}\s", result.stdout, re.M), code
    assert "odczekaj przed" in result.stdout


@pytest.mark.parametrize(
    ("mode", "options"),
    [
        ("api", ["--save", "--max-wait", "--trim", "--full"]),
        ("page", ["--prop", "--save", "--max-wait", "--trim", "--full"]),
    ],
)
def test_mode_help_lists_options(tmp_path: Path, mode: str, options: list[str]) -> None:
    result = run_script(mode, "--help", cwd=tmp_path)

    assert result.returncode == 0, result.stderr
    for option in options:
        assert option in result.stdout
    assert "kody wyjścia" in result.stdout


def test_config_is_imported_first_and_file_parses_on_old_python() -> None:
    """config's version check can only run if Python 3.9 compiles probe.py first."""
    source = PROBE.read_text(encoding="utf-8")
    ast.parse(source, feature_version=(3, 9))
    body = ast.parse(source).body
    first = body[1] if isinstance(body[0], ast.Expr) else body[0]  # skip the docstring

    assert isinstance(first, ast.ImportFrom)
    assert first.module == "config"
