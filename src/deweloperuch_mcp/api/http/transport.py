"""HTTP transport to deweloperuch.pl: one GET per call under the D2 policy, plus a cache.

Every call:

- requests only documented read channels (``deweloperuch_mcp.allowlist``), never the
  dumps of D5 nor ``valuation-pdf``; anything else is an ``InvalidInputError`` before
  the cache and the limiter are even looked at;

and every call that is not served from the cache:

- waits for and holds the shared limiter slot (``deweloperuch_mcp.throttle``: 1 request
  at a time, at least 1 s apart, across processes) for the whole exchange, body included;
- sends the one User-Agent (``identity.USER_AGENT``, D9) to ``identity.BASE_URL``;
- records the pause a 429 or 502/503/504 asks for (``http_policy.pause_seconds``) as soon
  as the headers arrive, so it counts even if reading the body fails;
- stops on 401, 403, 429 and Cloudflare challenges (``http_policy.stop_reason``), and
  then for good: the process remembers the first STOP (one latch for every client in
  it) and every later call that would need the network raises it again without
  sending anything (CONTRIBUTING.md: stop and report); only a new process may try again.
  The STOP is latched before the limiter slot is released and checked again inside
  the slot, so a thread waiting for its turn never sends after another one's STOP;
- records that STOP for every other process too (``Slot.stop``, source ``pakiet``),
  before the slot is released; a STOP the headers already show (401, 403, 429,
  ``cf-mitigated``) is latched and recorded before the body is read, so an interrupted
  read cannot lose it. A STOP recorded by any process (also ``recon/``) makes the
  limiter refuse the slot (``StoppedError``), which becomes the same
  ``ServiceBlockedError`` (``RateLimitedError`` while a 429 lasts) and is latched too.
  A 429 ends with its pause; anything else lasts until a person removes the record.
  STOP messages tell a model to stop and report, nothing else (no waiting, no
  restarting, no lifting); times, sources and pauses are in ``detail``;
- never retries and never follows redirects;
- reads at most ``max_body_bytes`` (``http_policy.MAX_BODY_BYTES``, dumps are refused,
  D5) within ``BODY_DEADLINE``.

Successful bodies are cached in memory for what is left of their freshness after the
``Age`` they already spent in Cloudflare's cache, at most ``DEFAULT_TTL``, or for
``DEFAULT_TTL`` when Cloudflare serves them past their freshness (``_ttl``), and only
after the caller's ``decode`` accepted them, so a body that does not match the
contract (or says "not found") is never served again from the cache.

Synchronous on purpose: the MCP server (S1b) runs calls with ``asyncio.to_thread``, which
keeps the limiter slot's enter and exit in one thread, as ``RequestLimiter.slot`` requires.
"""

import contextlib
import logging
import math
import re
import threading
import time
import urllib.parse
from collections import OrderedDict
from collections.abc import Callable, Collection, Mapping, Sequence
from dataclasses import dataclass
from types import TracebackType
from typing import Self, TypeVar

import httpx

from deweloperuch_mcp.allowlist import match_api, match_dump, match_excluded_api, match_page
from deweloperuch_mcp.http_policy import (
    MAX_BODY_BYTES,
    PAUSE_AFTER_429,
    body_length,
    is_html,
    pause_seconds,
    stop_cause,
    stop_reason,
)
from deweloperuch_mcp.identity import BASE_URL, USER_AGENT
from deweloperuch_mcp.models.errors import (
    SERVICE_CHANGED,
    InvalidInputError,
    LimiterWaitError,
    NotFoundError,
    RateLimitedError,
    ServiceBlockedError,
    ServiceError,
    SessionClosedError,
    UnexpectedResponseError,
)
from deweloperuch_mcp.retry_after import parse_retry_after
from deweloperuch_mcp.throttle import (
    DEFAULT_MAX_WAIT,
    MAX_DEFER,
    STOP_INSTRUCTION,
    RequestLimiter,
    Slot,
    StoppedError,
    StopRecord,
    WaitTooLongError,
    format_time,
)

T = TypeVar("T")

_log = logging.getLogger(__name__)


@dataclass(frozen=True)
class _Latched:
    """The first STOP of the process: its error and its reason in a few words
    (``http_policy.stop_reason`` or the record's label), repeated by later calls."""

    error: ServiceBlockedError
    reason: str


# The STOP latch of the process: the first STOP of any HttpClient. Read and set under the
# lock; set inside the limiter slot (HttpClient._fetch).
_stop_lock = threading.Lock()
_stop: _Latched | None = None


def _stopped() -> _Latched | None:
    with _stop_lock:
        return _stop


def _latch_stop(error: ServiceBlockedError, reason: str) -> None:
    global _stop
    with _stop_lock:
        if _stop is None:
            _stop = _Latched(error, reason)


STOP_SOURCE = "pakiet"
"""``source`` of the STOP records this client writes (``recon/`` writes its own names)."""

TIMEOUT = 30.0
"""Seconds for connecting and for each read from the socket (as in ``recon/``)."""

BODY_DEADLINE = 120.0
"""Seconds for reading a body; checked after each chunk."""

NOT_FOUND = 404
"""The status of what the service does not know, unless an endpoint says otherwise."""

DEFAULT_TTL = 300.0
"""Longest a reply stays in the in-memory cache (D2), whatever its headers say; also its
freshness when ``Cache-Control`` gives neither ``s-maxage`` nor ``max-age``."""

CACHE_ENTRIES = 256
CACHE_BYTES = 64 * 1024 * 1024
"""Bounds of the in-memory cache; the least recently used entries go first."""

# A service path with an optional query: printable ASCII, already percent-encoded, no
# host (`//...`), no fragment, no spaces.
_TARGET = re.compile(r"/(?!/)[A-Za-z0-9._~!$&'()*+,;=:@/%?-]*")
_S_MAXAGE = re.compile(r'(?:^|,)\s*s-maxage\s*=\s*"?([0-9]+)"?\s*(?:,|$)', re.IGNORECASE)
_MAX_AGE = re.compile(r'(?:^|,)\s*max-age\s*=\s*"?([0-9]+)"?\s*(?:,|$)', re.IGNORECASE)
_NO_CACHE = re.compile(r"(?:^|,)\s*no-(?:store|cache)\s*(?:[,=]|$)", re.IGNORECASE)


@dataclass(frozen=True)
class Reply:
    """A complete 2xx response, as handed to ``decode``."""

    status: int
    headers: httpx.Headers
    body: bytes


@dataclass(frozen=True)
class Problem:
    """Why a body is unusable: the message for people and models, and the detail."""

    message: str
    detail: str


class ResponseCache:
    """In-memory LRU cache of replies with a TTL; thread-safe."""

    def __init__(
        self,
        *,
        max_entries: int = CACHE_ENTRIES,
        max_bytes: int = CACHE_BYTES,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._max_entries = max_entries
        self._max_bytes = max_bytes
        self._clock = clock
        self._entries: OrderedDict[str, tuple[float, Reply]] = OrderedDict()
        self._bytes = 0
        self._lock = threading.Lock()

    def get(self, key: str) -> Reply | None:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            expires, reply = entry
            if self._clock() >= expires:
                self._remove(key)
                return None
            self._entries.move_to_end(key)
            return reply

    def put(self, key: str, reply: Reply, ttl: float) -> None:
        if ttl <= 0 or len(reply.body) > self._max_bytes:
            return
        with self._lock:
            self._remove(key)
            self._entries[key] = (self._clock() + ttl, reply)
            self._bytes += len(reply.body)
            while len(self._entries) > self._max_entries or self._bytes > self._max_bytes:
                self._remove(next(iter(self._entries)))

    def _remove(self, key: str) -> None:
        entry = self._entries.pop(key, None)
        if entry is not None:
            self._bytes -= len(entry[1].body)


class HttpClient:
    """GETs to deweloperuch.pl through the shared limiter; see the module docstring.

    ``limiter`` defaults to ``RequestLimiter()`` (the lock shared with ``recon/``);
    ``max_wait`` is the longest pause it may impose before a call raises
    ``LimiterWaitError``. ``max_body_bytes`` may only be lowered. ``clock`` (wall clock,
    for ``Retry-After`` dates) and ``monotonic`` (cache TTL, body deadline) are injectable
    for tests.
    """

    @staticmethod
    def target(path: str, params: Sequence[tuple[str, str | int]] = ()) -> str:
        """``path?name=value&...`` with every name and value percent-encoded, in the given order.

        The order is kept so the same request always has the same URL (cache keys, the RSC
        ``_rsc`` token).
        """
        query = urllib.parse.urlencode(
            [(name, str(value)) for name, value in params], quote_via=urllib.parse.quote, safe=""
        )
        return f"{path}?{query}" if query else path

    @staticmethod
    def segment(value: str) -> str:
        """``value`` as one percent-encoded path segment (``/``, ``?``, ``#`` included)."""
        return urllib.parse.quote(value, safe="")

    @staticmethod
    def testing_only_reset_stop() -> None:
        """Forget the process's STOP. Tests only: in production a STOP lasts until the process
        ends (CONTRIBUTING.md: stop and report, never retry)."""
        global _stop
        with _stop_lock:
            _stop = None

    def __init__(  # noqa: PLR0913 - keyword-only limiter, cache and clocks, injected by tests
        self,
        *,
        limiter: RequestLimiter | None = None,
        max_wait: float = DEFAULT_MAX_WAIT,
        max_body_bytes: int = MAX_BODY_BYTES,
        cache: ResponseCache | None = None,
        clock: Callable[[], float] = time.time,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        if not 0 < max_body_bytes <= MAX_BODY_BYTES:
            raise ValueError(
                f"max_body_bytes musi być w zakresie 1..{MAX_BODY_BYTES} (D5: bez zrzutów), "
                f"podano {max_body_bytes!r}"
            )
        self._limiter = limiter if limiter is not None else RequestLimiter()
        self._max_wait = max_wait
        self._max_body_bytes = max_body_bytes
        self._cache = cache if cache is not None else ResponseCache(clock=monotonic)
        self._clock = clock
        self._monotonic = monotonic
        self._http = httpx.Client(
            headers={"User-Agent": USER_AGENT},
            follow_redirects=False,
            timeout=httpx.Timeout(TIMEOUT),
        )

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    @property
    def closed(self) -> bool:
        return self._http.is_closed

    def get(
        self,
        target: str,
        *,
        headers: Mapping[str, str],
        decode: Callable[[Reply], T],
        unknown: Collection[int] = (NOT_FOUND,),
        gone: Collection[int] = (),
    ) -> T:
        """GET ``target`` (path with an encoded query) and ``decode`` the 2xx reply.

        ``unknown``: the statuses that mean the service does not know what was asked for
        (``NotFoundError``); 404 unless the endpoint answers so in another way. ``gone``:
        the statuses that mean the channel itself is no longer there, whatever was asked
        (``UnexpectedResponseError``: the data source is unavailable, not the object); a
        status in both is ``unknown`` unless the reply is an HTML page.

        Served from the cache when a reply for the same target and headers is fresh.
        Raises the errors of ``deweloperuch_mcp.errors``, checked in this order:
        ``InvalidInputError`` for a target off the read allowlist (a bug in the program;
        nothing looked up, nothing sent); ``SessionClosedError`` after ``close()``; then
        the cache; after a STOP anywhere in this process, the same
        ``ServiceBlockedError`` for every call the cache cannot answer. ``decode`` raises
        ``UnexpectedResponseError`` for data that does not match the contract.
        """
        _check_target(target)
        if self._http.is_closed:
            raise SessionClosedError(
                "Sesja z deweloperuch.pl jest już zamknięta, więc zapytanie nie zostało "
                "wysłane. Otwórz nową sesję (Session())."
            )
        sent = {name: value for name, value in headers.items() if name.lower() != "user-agent"}
        sent["User-Agent"] = USER_AGENT
        key = "\n".join([target, *sorted(f"{k.lower()}: {v}" for k, v in sent.items())])
        cached = self._cache.get(key)
        if cached is not None:
            return decode(cached)
        stopped = _stopped()
        if stopped is not None:
            raise _still_stopped(stopped)
        reply, ttl = self._fetch(target, sent, unknown, gone)
        value = decode(reply)
        self._cache.put(key, reply, ttl)
        return value

    # --- one request -------------------------------------------------------------------

    def _fetch(
        self,
        target: str,
        headers: Mapping[str, str],
        unknown: Collection[int],
        gone: Collection[int],
    ) -> tuple[Reply, float]:
        try:
            with self._limiter.slot(max_wait=self._max_wait) as slot:
                # Again in the slot: another thread may have hit a STOP while this one
                # waited for its turn (it latches the STOP before releasing the slot).
                stopped = _stopped()
                if stopped is not None:
                    raise _still_stopped(stopped)
                response, body, problem, pause = self._exchange(slot, target, headers)
                reply = Reply(response.status_code, response.headers, body)
                try:
                    _check(target, reply, problem, pause, unknown, gone=gone)
                except ServiceBlockedError as err:
                    # Both before the slot is released: the latch for the threads of this
                    # process (see above), the record for every other process.
                    why = stop_reason(reply.status, reply.headers, reply.body) or "STOP"
                    _latch_stop(err, why)
                    _record_stop(slot, reply, err)
                    raise
                return reply, _ttl(response.headers)
        except StoppedError as err:
            # A STOP recorded earlier, maybe by another process; this process's own STOP,
            # if it has one, says more (the first answer, its pause).
            latched = _stopped()
            if latched is not None:
                raise _still_stopped(latched) from err
            blocked = _blocked_by_record(err)
            stop = err.stop
            label = stop.label if isinstance(stop, StopRecord) else _UNREADABLE_REASON
            _latch_stop(blocked, label)
            raise blocked from err
        except WaitTooLongError as err:
            raise LimiterWaitError(
                f"{err} Zapytanie nie zostało wysłane.", wait_seconds=err.remaining
            ) from err

    def _exchange(
        self, slot: Slot, target: str, headers: Mapping[str, str]
    ) -> tuple[httpx.Response, bytes, Problem | None, float | None]:
        try:
            with self._http.stream("GET", BASE_URL + target, headers=headers) as response:
                pause = self._pause(slot, response)
                _stop_early(slot, target, response, pause)
                body, problem = self._read_body(response)
        except httpx.HTTPError as err:
            raise ServiceError(
                "Błąd sieci: brak odpowiedzi serwisu deweloperuch.pl. Nic nie ponawiam; "
                "spróbuj później.",
                detail=f"{target}: {err!r}",
            ) from err
        return response, body, problem, pause

    def _pause(self, slot: Slot, response: httpx.Response) -> float | None:
        """Record the pause the response asks for before anything else can fail."""
        asked = parse_retry_after(response.headers.get("retry-after"), self._clock())
        seconds = pause_seconds(response.status_code, asked)
        if seconds is None:
            return None
        try:
            slot.defer(seconds)
        except ValueError:
            return MAX_DEFER  # defer() recorded its cap before refusing the rest
        return seconds

    def _read_body(self, response: httpx.Response) -> tuple[bytes, Problem | None]:
        limit = self._max_body_bytes
        too_big = Problem(
            "Odpowiedź serwisu jest za duża: klient nie pobiera tak dużych danych. Zawęź "
            "zapytanie (filtry, mniejszy zakres).",
            f"ponad {limit} B (zrzut, D5)",
        )
        text = (body_length(response.status_code, response.headers) or "").strip()
        declared = int(text) if text.isascii() and text.isdigit() else None
        if declared is not None and declared > limit:
            return b"", too_big
        chunks: list[bytes] = []
        size = 0
        start = self._monotonic()
        try:
            for chunk in response.iter_bytes():
                chunks.append(chunk)
                size += len(chunk)
                if size > limit:
                    return b"".join(chunks)[:limit], too_big
                if self._monotonic() - start > BODY_DEADLINE:
                    return b"".join(chunks), Problem(
                        f"Serwis odpowiadał za długo (ponad {BODY_DEADLINE:g} s). Nic nie "
                        "ponawiam; spróbuj później.",
                        f"przeczytano {size} B",
                    )
        except httpx.HTTPError as err:
            return b"".join(chunks), Problem(
                "Połączenie z serwisem zostało przerwane w trakcie odpowiedzi. Nic nie "
                "ponawiam; spróbuj później.",
                f"przeczytano {size} B: {err!r}",
            )
        # Content-Length counts bytes on the wire, before Content-Encoding is undone.
        if declared is not None and response.num_bytes_downloaded < declared:
            return b"".join(chunks), Problem(
                "Odpowiedź serwisu jest ucięta. Nic nie ponawiam; spróbuj później.",
                f"{response.num_bytes_downloaded} z {declared} B",
            )
        return b"".join(chunks), None


_PROGRAM_BUG = "Błąd programu (zgłoś go autorom, to nie błąd danych wejściowych): "


def _check_target(target: str) -> None:
    """A documented read channel, checked as the server will see it (D1, D5, CONTRIBUTING.md).

    The adapters build every target, so a violation is a bug in the program; the
    message says so (``InvalidInputError`` without a type of its own).
    """
    if not _TARGET.fullmatch(target):
        raise InvalidInputError(
            f"{_PROGRAM_BUG}nieprawidłowy adres zapytania.",
            detail=(
                "oczekiwano ścieżki serwisu z zakodowanym query (np. /api/cities?q=krak), "
                f"podano {target!r}"
            ),
        )
    path = target.split("?", 1)[0]
    # The allowlist matches the path as written; the server decodes `%2F` and resolves
    # `..`, so such paths could reach something else than what was checked.
    if "%" in path or any(segment in (".", "..") for segment in path.split("/")):
        raise InvalidInputError(
            f"{_PROGRAM_BUG}nieprawidłowy adres zapytania.",
            detail=(
                f"ścieżka {path!r} nie może zawierać kodowania % ani segmentów . i ..: "
                "slugi to zwykłe znaki ASCII"
            ),
        )
    if match_excluded_api(path) is not None or match_dump(path) is not None:
        raise InvalidInputError(
            f"{_PROGRAM_BUG}zapytanie o dane poza zakresem klienta.",
            detail=f"{path} jest poza zakresem klienta (zrzuty D5, valuation-pdf)",
        )
    if match_api(path) is None and match_page(path) is None:
        raise InvalidInputError(
            f"{_PROGRAM_BUG}zapytanie spoza udokumentowanych kanałów odczytu.",
            detail=(
                f"{path} jest spoza allowlisty odczytu (docs/discovery/endpoints.md, pages-rsc.md)"
            ),
        )


def _stop_early(slot: Slot, target: str, response: httpx.Response, pause: float | None) -> None:
    """Latch and record a STOP that the status and headers already show, before the body.

    401, 403, 429 and ``cf-mitigated``: an interrupted read of the body (Ctrl+C, SIGTERM,
    a timeout of the caller) must not lose them. A challenge seen only in the HTML comes
    after the body (``_fetch``); the record keeps whichever came first. A record that
    cannot be written here is tried again after the body, which reports the failure.
    """
    why = stop_reason(response.status_code, response.headers, b"")
    error = _stop_error(target, response.status_code, response.headers, b"", pause)
    cause = stop_cause(response.status_code, response.headers, b"")
    if why is None or error is None or cause is None:
        return
    # Known: a 403 whose HTML turns out to be a challenge keeps "HTTP 403" here, while the
    # caller then gets "…, challenge Cloudflare"; both STOPs are permanent anyway.
    _latch_stop(error, why)
    with contextlib.suppress(OSError, ValueError):
        slot.stop(cause[0], cause[1], source=STOP_SOURCE)


def _record_stop(slot: Slot, reply: Reply, error: ServiceBlockedError) -> None:
    """Record the STOP for every process; a failure only goes to ``error.detail``.

    The STOP itself must reach the caller whatever happens to the record.
    """
    cause = stop_cause(reply.status, reply.headers, reply.body)
    if cause is None:  # never: _check stops exactly when stop_cause has a cause
        return
    status, reason = cause
    try:
        slot.stop(status, reason, source=STOP_SOURCE)
    except (OSError, ValueError) as err:
        error.detail = f"{error.detail}; STOP nie został zapisany dla innych procesów: {err!r}"


def _blocked_by_record(stopped: StoppedError) -> ServiceBlockedError:
    """The error of a call refused by an earlier STOP record; nothing was sent.

    The message is the limiter's (no times, no source); they go to ``detail``.
    """
    stop = stopped.stop
    if isinstance(stop, StopRecord):
        detail = f"zapis STOP: {stop.summary()}"
        if stop.pid is not None:
            detail += f", PID {stop.pid}"
        if stop.until is not None:
            detail += f", do {format_time(stop.until)}"
    else:
        detail = f"nieczytelny zapis STOP: {stop.problem}"
    if stopped.seconds_left is not None:  # a 429 that has not ended yet
        return RateLimitedError(str(stopped), stopped.seconds_left, detail=detail)
    return ServiceBlockedError(str(stopped), detail=detail)


_UNREADABLE_REASON = "nieczytelny zapis o wcześniejszym STOP"
"""The reason a later call repeats after a STOP from an unreadable record."""


def _still_stopped(first: _Latched) -> ServiceBlockedError:
    """The error of a call after a STOP: the same type and detail, nothing sent."""
    message = (
        "STOP: seria zapytań do deweloperuch.pl jest już przerwana; zapytanie nie zostało "
        f"wysłane. Powód: {first.reason}. {STOP_INSTRUCTION}"
    )
    error = first.error
    if isinstance(error, RateLimitedError):
        return RateLimitedError(message, error.pause_seconds, detail=error.detail)
    return ServiceBlockedError(message, detail=error.detail)


def _stop_error(
    target: str, status: int, headers: httpx.Headers, body: bytes, pause: float | None
) -> ServiceBlockedError | None:
    """The STOP of an answer (``http_policy.stop_reason``), ``None`` for no STOP.

    The message tells a model only to stop and report: nothing about waiting, restarting
    or lifting anything. The pause of a 429 is in ``pause_seconds`` and, with the target
    and the status, in ``detail``.
    """
    why = stop_reason(status, headers, body)
    if why is None:
        return None
    message = (
        f"STOP: {why}. Klient nie wyśle już żadnego zapytania; inne procesy też zostały "
        f"wstrzymane. {STOP_INSTRUCTION}"
    )
    detail = f"{target}: HTTP {status}"
    if pause is not None:
        detail += f", pauza limitera {math.ceil(pause)} s"
    if status == 429:
        waited = pause if pause is not None else PAUSE_AFTER_429
        return RateLimitedError(message, waited, detail=detail)
    return ServiceBlockedError(message, detail=detail)


def _check(  # noqa: PLR0913 - the reply, then what its statuses mean for this channel
    target: str,
    reply: Reply,
    problem: Problem | None,
    pause: float | None,
    unknown: Collection[int] = (NOT_FOUND,),
    *,
    gone: Collection[int] = (),
) -> None:
    """Raise for anything but a complete 2xx. STOP first, whatever else is wrong.

    Messages say what happened and what to do; the target, the status and an excerpt of
    the body go to ``detail`` (an answer of the service is not text for a model).
    """
    status = reply.status
    after = "" if pause is None else f" Limiter wstrzyma następne zapytanie o {math.ceil(pause)} s."
    stopped = _stop_error(target, status, reply.headers, reply.body, pause)
    if stopped is not None:
        raise stopped
    if problem is not None:
        raise ServiceError(
            f"{problem.message}{after}", pause, detail=f"{target}: HTTP {status}, {problem.detail}"
        )
    if 300 <= status < 400:
        location = reply.headers.get("location", "?")
        raise ServiceError(
            f"Serwis przekierował zapytanie gdzie indziej (HTTP {status}); klient nie podąża "
            "za przekierowaniami.",
            pause,
            detail=f"{target} -> {location}",
        )
    if _is_gone(reply, unknown, gone):
        raise UnexpectedResponseError(
            f"Źródło danych tego narzędzia nie jest już dostępne w serwisie (HTTP {status}). "
            f"{SERVICE_CHANGED}",
            detail=f"{target}: HTTP {status}, kanał odczytu zniknął z serwisu",
        )
    if status == NOT_FOUND and status in unknown:
        raise NotFoundError("Serwis nie zna żądanych danych (HTTP 404).", detail=target)
    if status in unknown:
        raise NotFoundError(
            f"Serwis nie zna żądanych danych (HTTP {status}).",
            detail=f"{target}: {_excerpt(reply.body)}",
        )
    if not 200 <= status < 300:
        raise ServiceError(
            f"Serwis odpowiedział błędem HTTP {status}. Nic nie ponawiam; spróbuj później.{after}",
            pause,
            detail=f"{target}: {_excerpt(reply.body)}",
        )


def _is_gone(reply: Reply, unknown: Collection[int], gone: Collection[int]) -> bool:
    """The reply says the channel itself is no longer there. A status both in ``gone`` and
    in ``unknown`` is the endpoint's own answer (e.g. its JSON error) unless an HTML page
    came instead: then the route itself is missing."""
    if reply.status not in gone:
        return False
    return reply.status not in unknown or is_html(reply.headers, reply.body)


def _ttl(headers: httpx.Headers) -> float:
    """Seconds the cache may serve a reply: its freshness left, at most ``DEFAULT_TTL`` (D2).

    Freshness is ``s-maxage`` (Cloudflare's), else ``max-age``, else ``DEFAULT_TTL``;
    what is left is that minus ``Age``, how long the reply already sat in Cloudflare's
    cache. Nothing left (``Age`` at or above the freshness): ``DEFAULT_TTL`` (D2,
    clarification of 2026-10-13: Cloudflare serves such a copy, e.g. the GUS page
    ``polska`` with ``age: 69574`` at ``max-age=28800`` [P 2026-10-13], and a repeat
    within 5 minutes would get it again). Not cached: ``no-store`` or ``no-cache`` (any
    case, with or without a value), and a freshness of 0 (``max-age=0``: the origin asks
    for no reuse, as ``no-cache``). Unreadable values (not ASCII digits) are ignored.
    The service sends ``max-age=28800`` without ``s-maxage`` for RSC pages and most
    ``/api/*`` (docs/discovery, [P 2026-10-10]) with an ``Age`` of thousands of seconds,
    so counting from ``s-maxage`` alone left them uncached. ``private`` and
    ``must-revalidate`` are not read: this cache is private to one process.
    """
    control = headers.get("cache-control", "")
    age_text = headers.get("age", "").strip()
    if _NO_CACHE.search(control):
        ttl = 0.0
    else:
        found = _S_MAXAGE.search(control) or _MAX_AGE.search(control)
        fresh = DEFAULT_TTL if found is None else float(found[1])
        age = float(age_text) if age_text.isascii() and age_text.isdigit() else 0.0
        if fresh <= 0:
            ttl = 0.0
        elif age >= fresh:  # served past its freshness by Cloudflare: 5 minutes (D2)
            ttl = DEFAULT_TTL
        else:
            ttl = min(DEFAULT_TTL, fresh - age)
    _log.debug("TTL cache %g s (Cache-Control: %r, Age: %r)", ttl, control, age_text)
    return ttl


def _excerpt(body: bytes, limit: int = 300) -> str:
    """The start of a body on one line, for ``detail`` (never for messages).

    Control characters are escaped where the detail is shown (``consumers.shared.text``).
    """
    text = " ".join(body[: limit * 4].decode("utf-8", "replace").split())
    return text[:limit] + ("…" if len(text) > limit or len(body) > limit * 4 else "")
