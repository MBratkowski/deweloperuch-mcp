"""One GET to deweloperuch.pl for recon scripts: transport, limiter slot, checks (stdlib only).

Shared by ``recon/probe.py`` and ``recon/scan_bundles.py``. The response policy itself
(what stops a series, how long to pause, the body limit) lives in the package
(``deweloperuch_mcp.http_policy``, through config) so the package's client follows it
too; this module adds what needs urllib and the limiter:

- ``urllib_fetch``: one GET, no redirects, no retries, error statuses returned;
- ``read_body``: the body within ``MAX_BODY_BYTES`` and ``BODY_DEADLINE``;
- ``get_once``: one request inside a limiter slot; the pause and a STOP (for every
  process, ``record_stop``) recorded before leaving it. A STOP recorded earlier by any
  process makes the limiter refuse the slot (``StoppedError``): nothing is sent.
  Known limit: ``fetch`` returns only after the body (``read_body``, up to
  ``BODY_DEADLINE``), so unlike the package's client, recon records a STOP after the
  body, not right after the headers. A run killed while reading the body of a 401, 403
  or 429 (Ctrl+C, SIGTERM, a timeout of the caller) leaves no record, though the next
  run still waits ``min_interval``. Closing it needs a headers callback in ``Fetch``,
  which every transport and test double would have to take;
- ``check_reply``: anything but a usable 2xx raises ``ReplyError``.

Imported after config by the scripts, so it may use syntax newer than Python 3.9.
"""

# config goes first: it stops Python < 3.11 with a clear message and puts src/ on sys.path.
from config import (
    MAX_BODY_BYTES,
    RequestLimiter,
    Slot,
    body_length,
    content_type,
    parse_retry_after,
    pause_seconds,
    stop_cause,
    stop_reason,
)

# isort: split
import http.client
import math
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from email.message import Message
from typing import Literal, Protocol

TIMEOUT = 30.0
"""Seconds for connecting and for each read from the socket."""

BODY_DEADLINE = 120.0
"""Seconds for reading the body. Checked after each ``read1`` (one socket read, bounded
by TIMEOUT), plus one last read to see EOF, so the worst case is about
BODY_DEADLINE + 2 x TIMEOUT (a chunked body may add a chunk-header read per call)."""

_CHUNK = 64 * 1024


@dataclass(frozen=True)
class Response:
    """What recon needs from an HTTP response. Header names are lowercase.

    ``body_error`` says why the body is incomplete (too big, too slow, connection lost
    while reading); the status and headers are still valid, so a 429 still pauses the
    limiter and stops the series.
    """

    status: int
    headers: Mapping[str, str]
    body: bytes
    body_error: str | None = None


class Readable(Protocol):
    """A response stream as ``read_body`` uses it (urllib's response or HTTPError).

    ``read1`` returns after one read from the socket, unlike ``read``, which blocks until
    ``size`` bytes or EOF and so would let a trickling body outlast ``BODY_DEADLINE``.
    """

    def read1(self, size: int, /) -> bytes: ...


Fetch = Callable[[str, Mapping[str, str], float], Response]
"""``fetch(url, headers, timeout)``: one GET, any status returned, never a redirect."""


class NetworkError(Exception):
    """No response at all (timeout, refused or reset connection); nothing to retry."""


ReplyKind = Literal["stop", "redirect", "http"]


class ReplyError(Exception):
    """A response that is not a usable 2xx.

    ``kind``: ``"stop"`` (401, 403, 429, challenge: end the whole series), ``"redirect"``
    (3xx, not followed; the caller adds what to do about it) or ``"http"`` (any other
    status, or an incomplete body).
    """

    def __init__(self, kind: ReplyKind, message: str) -> None:
        super().__init__(message)
        self.kind = kind


# --- transport ----------------------------------------------------------------------


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Hands a 3xx back to the caller: one call is exactly one request."""

    def redirect_request(self, *_args: object, **_kwargs: object) -> None:
        """No new request for any redirect (urllib's signature: req, fp, code, msg, headers,
        newurl)."""


def urllib_fetch(url: str, headers: Mapping[str, str], timeout: float) -> Response:
    """GET ``url`` once: no redirects, no retries; error statuses are returned, not raised."""
    opener = urllib.request.build_opener(_NoRedirect)
    request = urllib.request.Request(url, headers=dict(headers), method="GET")
    try:
        with opener.open(request, timeout=timeout) as reply:
            return _response(reply.status, reply.headers, reply)
    except urllib.error.HTTPError as err:
        with err:
            return _response(err.code, err.headers, err)


def _response(status: int, message: Message, stream: Readable) -> Response:
    headers = _header_map(message)
    body, problem = read_body(stream, body_length(status, headers))
    return Response(status, headers, body, problem)


def read_body(
    stream: Readable, content_length: str | None, clock: Callable[[], float] = time.monotonic
) -> tuple[bytes, str | None]:
    """The body, read in chunks within ``MAX_BODY_BYTES`` and ``BODY_DEADLINE``.

    Returns ``(body, problem)``. The response has already arrived, so its status must
    still count: a read failing with ``OSError`` (timeout, reset), ``ValueError``
    (closed stream) or ``http.client.HTTPException`` (``IncompleteRead``, broken
    chunked encoding) becomes a problem instead of an exception. Anything else, e.g.
    ``AttributeError`` for a stream without ``read1``, is a bug and propagates.

    A declared ``Content-Length`` over the limit is refused before reading anything.
    Otherwise reading stops, keeping what was read, at the first byte over the limit,
    at a read error, or at the first chunk after the deadline; EOF right after the
    deadline still counts as a complete body. EOF before the declared ``Content-Length``
    is a truncated body: ``read1`` reports a connection closed early as plain EOF.
    """
    limit = MAX_BODY_BYTES
    too_big = (
        f"Odpowiedź przekracza {limit} B: recon nie służy do zrzutów (D5); "
        "użyj filtrów albo mniejszego zakresu."
    )
    text = (content_length or "").strip()
    # ASCII digits only, as [0-9]+ elsewhere: headers are latin-1, so "²" is a "digit" too.
    declared = int(text) if text.isascii() and text.isdigit() else None
    if declared is not None and declared > limit:
        return b"", too_big
    chunks: list[bytes] = []
    size = 0
    overdue = False
    start = clock()
    while True:
        try:
            chunk = stream.read1(min(_CHUNK, limit + 1 - size))
        except (OSError, ValueError, http.client.HTTPException) as err:
            return b"".join(chunks), f"Czytanie odpowiedzi przerwane ({size} B): {err!r}"
        if not chunk:  # EOF wins, also right after the deadline
            if declared is not None and size < declared:
                return b"".join(chunks), f"Odpowiedź ucięta: {size} z {declared} B."
            return b"".join(chunks), None
        chunks.append(chunk)
        size += len(chunk)
        if size > limit:
            return b"".join(chunks)[:limit], too_big
        if overdue:
            problem = f"Czytanie odpowiedzi przerwane po {BODY_DEADLINE:g} s ({size} B)."
            return b"".join(chunks), problem
        overdue = clock() - start > BODY_DEADLINE


def _header_map(message: Message) -> dict[str, str]:
    headers: dict[str, str] = {}
    for name, value in message.items():
        key = name.lower()
        headers[key] = f"{headers[key]}, {value}" if key in headers else str(value)
    return headers


# --- one request in the limiter -------------------------------------------------------


def get_once(  # noqa: PLR0913 - keyword-only transport, limiter and clock (test seams)
    url: str,
    headers: Mapping[str, str],
    *,
    fetch: Fetch,
    limiter: RequestLimiter,
    max_wait: float,
    now: Callable[[], float],
    source: str,
) -> tuple[Response, str | None]:
    """One GET inside the limiter slot; the pause and a STOP are recorded in it.

    ``source`` names the script in the STOP record (``probe``, ``scan_bundles``). Returns
    the response and notes about the pause and the STOP record (for stderr) or ``None``.
    Raises ``StoppedError`` (an earlier STOP of any process; nothing sent),
    ``WaitTooLongError`` (nothing sent) and ``NetworkError`` (no response). Never retries.
    """
    with limiter.slot(max_wait=max_wait) as slot:
        try:
            reply = fetch(url, headers, TIMEOUT)
        except (urllib.error.URLError, http.client.HTTPException, OSError) as err:
            raise NetworkError(
                f"Błąd sieci, brak odpowiedzi serwisu: {err}. Nie ponawiam."
            ) from err
        notes = [pause_limiter(slot, reply, now()), record_stop(slot, reply, source)]
    return reply, "\n".join(note for note in notes if note) or None


def record_stop(slot: Slot, reply: Response, source: str) -> str | None:
    """Record a STOP (401, 403, 429, challenge) for every process; the note goes to stderr.

    Call it after ``pause_limiter``: a 429 ends with the pause recorded there. ``None``
    when the reply is no STOP. A record that cannot be written is only a note: the STOP
    of this run stands anyway (``check_reply``).
    """
    cause = stop_cause(reply.status, reply.headers, reply.body)
    if cause is None:
        return None
    status, reason = cause
    try:
        slot.stop(status, reason, source=source)
    except (OSError, ValueError) as err:
        return f"Uwaga: STOP nie został zapisany dla innych procesów: {err}"
    # Also read by AI assistants running probe: say that, not when it ends or how to lift it.
    return "Zapisano STOP: inne procesy też zostały wstrzymane."


def pause_limiter(slot: Slot, reply: Response, now: float) -> str | None:
    """Pause the shared limiter after a 429 or a 502/503/504; the note goes to stderr.

    The length comes from ``http_policy.pause_seconds``; ``now`` (wall clock) is needed
    for a ``Retry-After`` given as a date.
    """
    raw = reply.headers.get("retry-after")
    asked = parse_retry_after(raw, now)
    seconds = pause_seconds(reply.status, asked)
    if seconds is None:
        return None
    if asked is not None:
        source = f"Retry-After {raw!r}"
    elif raw is None:
        source = "Brak Retry-After"
    else:
        source = f"Nieczytelny Retry-After {raw!r}"
    try:
        slot.defer(seconds)
    except ValueError as err:
        return f"{source}: {err}"
    return f"{source}: limiter wstrzyma następne zapytanie o {math.ceil(seconds)} s."


# --- checking the response ------------------------------------------------------------


def check_reply(reply: Response) -> None:
    """Raise ``ReplyError`` for anything but a usable 2xx; never retry.

    STOP comes first, also when the body is incomplete: a 429 or a challenge must end
    the series whatever else is wrong with the response.
    """
    status = reply.status
    why = stop_reason(status, reply.headers, reply.body)
    if why is not None:
        raise ReplyError(
            "stop",
            f"STOP: {why}. Przerwij serię zapytań, niczego nie ponawiaj i zgłoś to "
            "użytkownikowi (CONTRIBUTING.md: 401, 403, 429, captcha, WAF).",
        )
    if reply.body_error is not None:
        raise ReplyError("http", f"HTTP {status}. {reply.body_error}")
    if 300 <= status < 400:
        location = reply.headers.get("location", "?")
        raise ReplyError("redirect", f"HTTP {status}: przekierowanie na {location}.")
    if not 200 <= status < 300:
        raise ReplyError("http", f"HTTP {status}. Treść: {excerpt(reply.body)}")


def excerpt(body: bytes, limit: int = 300) -> str:
    """The start of a body on one line, for error messages."""
    text = " ".join(body[: limit * 4].decode("utf-8", "replace").split())
    return text[:limit] + ("…" if len(text) > limit or len(body) > limit * 4 else "")


def status_line(reply: Response) -> str:
    """``HTTP 200, text/html, 1234 B, cache-control: …`` for stderr."""
    parts = [f"HTTP {reply.status}", content_type(reply.headers) or "bez content-type"]
    parts.append(f"{len(reply.body)} B")
    parts.extend(
        f"{name}: {reply.headers[name]}"
        for name in ("cache-control", "cf-cache-status", "age")
        if name in reply.headers
    )
    return ", ".join(parts)
