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
  sending anything (CLAUDE.md: stop and report); only a new process may try again.
  The STOP is latched before the limiter slot is released and checked again inside
  the slot, so a thread waiting for its turn never sends after another one's STOP;
- never retries and never follows redirects;
- reads at most ``max_body_bytes`` (``http_policy.MAX_BODY_BYTES``, dumps are refused,
  D5) within ``BODY_DEADLINE``.

Successful bodies are cached in memory for what is left of ``s-maxage`` from
``Cache-Control`` (``DEFAULT_TTL`` without one) after the ``Age`` they already spent in
Cloudflare's cache, and only after the caller's ``decode`` accepted them, so a body that
does not match the contract is never served again from the cache.

Synchronous on purpose: the MCP server (S1b) runs calls with ``asyncio.to_thread``, which
keeps the limiter slot's enter and exit in one thread, as ``RequestLimiter.slot`` requires.
"""

import math
import re
import threading
import time
import urllib.parse
from collections import OrderedDict
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from types import TracebackType
from typing import Self, TypeVar

import httpx

from deweloperuch_mcp.allowlist import match_api, match_dump, match_excluded_api, match_page
from deweloperuch_mcp.errors import (
    InvalidInputError,
    LimiterWaitError,
    NotFoundError,
    RateLimitedError,
    ServiceBlockedError,
    ServiceError,
    SessionClosedError,
)
from deweloperuch_mcp.http_policy import (
    MAX_BODY_BYTES,
    PAUSE_AFTER_429,
    body_length,
    pause_seconds,
    stop_reason,
)
from deweloperuch_mcp.identity import BASE_URL, USER_AGENT
from deweloperuch_mcp.retry_after import parse_retry_after
from deweloperuch_mcp.throttle import (
    DEFAULT_MAX_WAIT,
    MAX_DEFER,
    RequestLimiter,
    Slot,
    WaitTooLongError,
)

T = TypeVar("T")

# The STOP latch of the process: the first ServiceBlockedError of any HttpClient. Read and
# set under the lock; set inside the limiter slot (HttpClient._fetch).
_stop_lock = threading.Lock()
_stop: ServiceBlockedError | None = None


def _stopped() -> ServiceBlockedError | None:
    with _stop_lock:
        return _stop


def _latch_stop(error: ServiceBlockedError) -> None:
    global _stop
    with _stop_lock:
        if _stop is None:
            _stop = error


def testing_only_reset_stop() -> None:
    """Forget the process's STOP. Tests only: in production a STOP lasts until the process
    ends (CLAUDE.md: stop and report, never retry)."""
    global _stop
    with _stop_lock:
        _stop = None


TIMEOUT = 30.0
"""Seconds for connecting and for each read from the socket (as in ``recon/``)."""

BODY_DEADLINE = 120.0
"""Seconds for reading a body; checked after each chunk."""

DEFAULT_TTL = 300.0
"""Cache TTL without ``s-maxage``: the shortest the service uses (offers, counters)."""

MAX_TTL = 86_400.0
"""Longest cache TTL: the longest ``s-maxage`` seen (RCN statistics, 24 h)."""

CACHE_ENTRIES = 256
CACHE_BYTES = 64 * 1024 * 1024
"""Bounds of the in-memory cache; the least recently used entries go first."""

# A service path with an optional query: printable ASCII, already percent-encoded, no
# host (`//...`), no fragment, no spaces.
_TARGET = re.compile(r"/(?!/)[A-Za-z0-9._~!$&'()*+,;=:@/%?-]*")
_S_MAXAGE = re.compile(r'(?:^|,)\s*s-maxage\s*=\s*"?([0-9]+)"?\s*(?:,|$)', re.IGNORECASE)


def build_target(path: str, params: Sequence[tuple[str, str | int]] = ()) -> str:
    """``path?name=value&...`` with every name and value percent-encoded, in the given order.

    The order is kept so the same request always has the same URL (cache keys, the RSC
    ``_rsc`` token).
    """
    query = urllib.parse.urlencode(
        [(name, str(value)) for name, value in params], quote_via=urllib.parse.quote, safe=""
    )
    return f"{path}?{query}" if query else path


def path_segment(value: str) -> str:
    """``value`` as one percent-encoded path segment (``/``, ``?``, ``#`` included)."""
    return urllib.parse.quote(value, safe="")


@dataclass(frozen=True)
class Reply:
    """A complete 2xx response, as handed to ``decode``."""

    status: int
    headers: httpx.Headers
    body: bytes


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

    def __init__(
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
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        self._http.close()

    @property
    def closed(self) -> bool:
        return self._http.is_closed

    def get(self, target: str, *, headers: Mapping[str, str], decode: Callable[[Reply], T]) -> T:
        """GET ``target`` (path with an encoded query) and ``decode`` the 2xx reply.

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
        reply, ttl = self._fetch(target, sent)
        value = decode(reply)
        self._cache.put(key, reply, ttl)
        return value

    # --- one request -------------------------------------------------------------------

    def _fetch(self, target: str, headers: Mapping[str, str]) -> tuple[Reply, float]:
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
                    _check(target, reply, problem, pause)
                except ServiceBlockedError as err:
                    _latch_stop(err)  # before the slot is released, see above
                    raise
                return reply, _ttl(response.headers)
        except WaitTooLongError as err:
            raise LimiterWaitError(
                f"{err} Zapytanie nie zostało wysłane.", wait_seconds=err.remaining
            ) from err

    def _exchange(
        self, slot: Slot, target: str, headers: Mapping[str, str]
    ) -> tuple[httpx.Response, bytes, str | None, float | None]:
        try:
            with self._http.stream("GET", BASE_URL + target, headers=headers) as response:
                pause = self._pause(slot, response)
                body, problem = self._read_body(response)
        except httpx.HTTPError as err:
            raise ServiceError(
                f"Błąd sieci, brak odpowiedzi serwisu deweloperuch.pl: {err!r}. Nie ponawiam."
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

    def _read_body(self, response: httpx.Response) -> tuple[bytes, str | None]:
        limit = self._max_body_bytes
        too_big = (
            f"Odpowiedź przekracza {limit} B: klient nie pobiera zrzutów (D5); "
            "zawęź zapytanie (filtry, mniejszy zakres)."
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
                    return b"".join(chunks), (
                        f"Czytanie odpowiedzi trwało za długo (ponad {BODY_DEADLINE:g} s, "
                        f"{size} B)."
                    )
        except httpx.HTTPError as err:
            return b"".join(chunks), f"Czytanie odpowiedzi przerwane ({size} B): {err!r}"
        # Content-Length counts bytes on the wire, before Content-Encoding is undone.
        if declared is not None and response.num_bytes_downloaded < declared:
            return b"".join(chunks), (
                f"Odpowiedź ucięta: {response.num_bytes_downloaded} z {declared} B."
            )
        return b"".join(chunks), None


_PROGRAM_BUG = "Błąd programu (zgłoś go autorom, to nie błąd danych wejściowych): "


def _check_target(target: str) -> None:
    """A documented read channel, checked as the server will see it (D1, D5, CLAUDE.md).

    The services build every target, so a violation is a bug in the program; the
    message says so (``InvalidInputError`` without a type of its own).
    """
    if not _TARGET.fullmatch(target):
        raise InvalidInputError(
            f"{_PROGRAM_BUG}oczekiwano ścieżki serwisu z zakodowanym query "
            f"(np. /api/cities?q=krak), podano {target!r}."
        )
    path = target.split("?", 1)[0]
    # The allowlist matches the path as written; the server decodes `%2F` and resolves
    # `..`, so such paths could reach something else than what was checked.
    if "%" in path or any(segment in (".", "..") for segment in path.split("/")):
        raise InvalidInputError(
            f"{_PROGRAM_BUG}ścieżka {path!r} nie może zawierać kodowania % ani segmentów "
            ". i ..: slugi to zwykłe znaki ASCII."
        )
    if match_excluded_api(path) is not None or match_dump(path) is not None:
        raise InvalidInputError(
            f"{_PROGRAM_BUG}{path} jest poza zakresem klienta (zrzuty D5, valuation-pdf); "
            "klient go nie wywołuje."
        )
    if match_api(path) is None and match_page(path) is None:
        raise InvalidInputError(
            f"{_PROGRAM_BUG}{path} jest spoza allowlisty odczytu "
            "(docs/discovery/endpoints.md, pages-rsc.md); klient woła tylko udokumentowane "
            "kanały odczytu."
        )


def _still_stopped(first: ServiceBlockedError) -> ServiceBlockedError:
    """The error of a call after a STOP: the same type, nothing sent."""
    message = (
        f"Seria zapytań do deweloperuch.pl jest przerwana do restartu procesu, a zapytanie "
        f"nie zostało wysłane. Wcześniej: {first}"
    )
    if isinstance(first, RateLimitedError):
        return RateLimitedError(message, first.pause_seconds)
    return ServiceBlockedError(message)


def _check(target: str, reply: Reply, problem: str | None, pause: float | None) -> None:
    """Raise for anything but a complete 2xx. STOP first, whatever else is wrong."""
    status = reply.status
    after = "" if pause is None else f" Limiter wstrzyma następne zapytanie o {math.ceil(pause)} s."
    why = stop_reason(status, reply.headers, reply.body)
    if why is not None:
        message = (
            f"STOP: {why}. Przerwij serię zapytań do deweloperuch.pl, niczego nie ponawiaj "
            f"i zgłoś to użytkownikowi. Klient nie wyśle już żadnego zapytania do restartu "
            f"procesu.{after}"
        )
        if status == 429:
            raise RateLimitedError(message, pause if pause is not None else PAUSE_AFTER_429)
        raise ServiceBlockedError(message)
    if problem is not None:
        raise ServiceError(f"HTTP {status}. {problem}{after}", pause)
    if 300 <= status < 400:
        location = reply.headers.get("location", "?")
        raise ServiceError(
            f"HTTP {status}: serwis przekierował {target} na {location}; klient nie podąża "
            "za przekierowaniami.",
            pause,
        )
    if status == 404:
        raise NotFoundError(f"HTTP 404: serwis nie zna {target}.")
    if not 200 <= status < 300:
        raise ServiceError(f"HTTP {status}. Treść: {_excerpt(reply.body)}{after}", pause)


def _ttl(headers: httpx.Headers) -> float:
    """Freshness left: ``s-maxage`` (``DEFAULT_TTL`` without one) minus ``Age``, capped.

    ``Age`` is how long the response already sat in Cloudflare's cache; anything but
    ASCII digits is ignored. Never below 0 (not cached) or above ``MAX_TTL``.
    """
    found = _S_MAXAGE.search(headers.get("cache-control", ""))
    fresh = DEFAULT_TTL if found is None else float(found[1])
    age_text = headers.get("age", "").strip()
    age = float(age_text) if age_text.isascii() and age_text.isdigit() else 0.0
    return min(max(fresh - age, 0.0), MAX_TTL)


def _excerpt(body: bytes, limit: int = 300) -> str:
    """The start of a body on one line, for error messages."""
    text = " ".join(body[: limit * 4].decode("utf-8", "replace").split())
    return text[:limit] + ("…" if len(text) > limit or len(body) > limit * 4 else "")
