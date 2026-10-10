"""Scan deweloperuch.pl JS bundles for data-layer entry points (drift detection, D7).

Downloads the HTML of a fixed list of representative pages (``PAGES``), collects every
Next.js chunk they reference (plus the chunks the webpack runtime loads lazily) and
prints:
  - the build ID of the deployed site,
  - every ``/api/...`` path literal found in client code,
  - every Next.js Server Action (exported name and id).

``--compare`` diffs the ``/api`` paths and the action *names* against a baseline
(``{"api": [...], "actions": [names]}``, written by ``--baseline-out``). Action ids and
the build ID change with every deploy and are not drift::

    python3 recon/scan_bundles.py [--json] [--compare PLIK] [--baseline-out PLIK]

- Every request goes through the shared limiter (1 request/s, one at a time, D2) with
  the one User-Agent (D9); no redirects, no retries. 401, 403, 429 and Cloudflare
  challenges stop the scan, any other failure ends it too (recon/http_common.py). A
  STOP is recorded for every process (source ``scan_bundles``), and a STOP recorded
  earlier by any process ends the scan before its next request.
- Only ``PAGES`` and ``/_next/static/chunks/*.js`` are requested (``is_scan_path``).
- Chunk file names carry a content hash, so a cached chunk is never fetched again: a
  second scan of the same build fetches only the pages. The cache
  (``default_cache_dir()``, files named by their path below ``/_next/static/chunks/``)
  also serves offline static analysis of the bundles.
- At most ``MAX_CHUNKS`` chunk requests per scan: an estimate stops the scan before
  them, and ``Scanner.chunk`` refuses the request over the limit in any case.
- A result that may be incomplete (chunks skipped or empty, no readable webpack runtime,
  build changed mid-scan) is printed with its reasons (``incomplete``), but
  ``--baseline-out`` refuses to save it and ``--compare`` ends with code 6, not 0 or 7.
- Live runs need the user's consent as long as U1 is open (D9).

Exit codes: ``EXIT_CODES_HELP`` (also in ``--help``).

Keep this file parseable by Python 3.9 (no ``match``, no ``except*``): Python compiles
the whole script before config's version check runs. Modules imported after config may
use newer syntax.
"""

# config goes first: it stops Python < 3.11 with a clear message and puts src/ on sys.path.
from config import (
    BASE_URL,
    DEFAULT_MAX_WAIT,
    USER_AGENT,
    RequestLimiter,
    StoppedError,
    WaitTooLongError,
    default_lock_dir,
    is_html,
)

# isort: split
import argparse
import contextlib
import dataclasses
import json
import os
import re
import stat
import sys
import tempfile
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeGuard

from flight import flight_from_html
from http_common import (
    Fetch,
    NetworkError,
    ReplyError,
    Response,
    check_reply,
    get_once,
    status_line,
    urllib_fetch,
)

# One page per route type is enough: chunks are per route, not per city.
PAGES = [
    "/",
    "/ceny-ofertowe/warszawa/mieszkania",
    "/ceny-ofertowe/warszawa/inwestycje",
    "/ceny-ofertowe/warszawa/deweloperzy",
    "/ceny-ofertowe/warszawa/deweloperzy/atal",
    "/ceny-ofertowe/warszawa/deweloperzy/atal/nowy-targowek-vi",
    "/ceny-ofertowe/warszawa/deweloperzy/atal/nowy-targowek-vi/raport-inwestycji",
    "/ceny-ofertowe/warszawa/mapa",
    "/ceny-transakcyjne/warszawa/mieszkania",
    "/ceny-transakcyjne/warszawa/domy",
    "/ceny-transakcyjne/warszawa/adresy",
    "/ceny-transakcyjne/warszawa/adresy/aleja-krakowska-279-warszawa",
    "/ceny-transakcyjne/warszawa/mapa",
    "/ceny-transakcyjne/polska/miasta",
    "/statystyki",
    "/statystyki/ceny-transakcyjne/mieszkania/warszawa/mapa",
    "/statystyki/statystyki-rzadowe/warszawa",
    "/statystyki/portale-ogloszeniowe/mieszkania/polska",
    "/wycena",
    "/kalkulator-oszczedzania",
    "/zglos-dewelopera",
    "/zglos-dewelopera/mapa-zgloszen",
]

CHUNKS_PREFIX = "/_next/static/chunks/"

CHUNK_RE = re.compile(r"/_next/static/chunks/[A-Za-z0-9_./\[\]%()-]+\.js")
API_RE = re.compile(r"""["'`](/api/[^"'`]*)""")
ACTION_RE = re.compile(
    r'createServerReference\)\("([0-9a-f]{40,})",[\w$]+\.callServer,void 0,'
    r'[\w$]+\.findSourceMapURL,"(\w+)"'
)
# webpack runtime: r.u=e=> ... "static/chunks/"+({id:"name"})[e]||e)+"."+({id:"hash"})[e]+".js"
LAZY_NAMES_RE = re.compile(
    r'"static/chunks/"\+\(\((\{[^}]*\})\)\[e\]\|\|e\)\+"\."\+\((\{[^}]*\})\)\[e\]'
)
LAZY_FIXED_RE = re.compile(r'"(static/chunks/[A-Za-z0-9_.-]+\.js)"')

# The only percent escapes chunk paths may carry: [ ] ( ) of dynamic segments and route
# groups. Any other one (also %25) could decode into a traversal, even on a server that
# decodes twice.
_ALLOWED_ESCAPE = re.compile(r"%(?:5[BD]|2[89])", re.IGNORECASE)
# A content hash in the file name: "page-0f3c1a2b3c4d5e6f.js", "1234.0f3c1a2b3c4d5e6f.js".
# [W] Next.js production chunk names pin their content (not in docs/discovery/); only
# names with such a hash are trusted from the cache, the rest is fetched every scan.
_HASHED_NAME = re.compile(r"(?:^|[-.])[0-9a-f]{8,}\.js$")
# The build ID is printed and goes into reports: a plain token only.
_BUILD_ID = re.compile(r"[A-Za-z0-9_.-]{1,100}")
_NEXT_DATA_BUILD_ID = re.compile(r'"buildId":"([^"\\]*)"')
# [W] docs/discovery/endpoints.md §6: row 0 of an RSC response is {…,"b":"<buildId>"}
# (documented for server action responses; assumed for the RSC payload of pages).
_FLIGHT_ROW_0 = re.compile(r"^0:", re.M)

MAX_CHUNKS = 400
"""Most chunk requests in one scan (no mass crawling, D2). The site has about 115 chunks.
A scan that would need more stops before fetching them (an estimate, from the cache);
``Scanner.chunk`` never sends request number ``MAX_CHUNKS + 1`` (a hard limit, also when
cached files turn out unreadable)."""

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_STOP = 3
EXIT_HTTP = 4
EXIT_WAIT = 5
EXIT_DATA = 6
EXIT_DRIFT = 7

STOP_SOURCE = "scan_bundles"
"""``source`` of the STOP records the scanner writes."""

EXIT_CODES_HELP = f"""\
kody wyjścia:
  0  sukces; z --compare: brak różnic względem baseline
  2  błąd użycia: zła opcja, --compare bez pliku albo z plikiem w złym formacie,
     --baseline-out wskazuje katalog albo nieistniejący katalog (wtedy skan się nie
     zaczyna); zapis --baseline-out się nie udał; zapytanie spoza allowlisty skanera
     (nie zostało wysłane)
  3  STOP: 401, 403, 429 albo challenge Cloudflare (captcha, WAF) na stronie lub
     chunku; skan przerwany: niczego nie ponawiaj i zgłoś to użytkownikowi (po 429
     limiter wstrzymuje następne zapytanie co najmniej na 60 s). STOP obowiązuje też
     inne procesy: także wcześniejszy STOP, wtedy skan przerwany przed zapytaniem
  4  inny błąd HTTP (3xx, pozostałe 4xx, 5xx), sieci (timeout, brak połączenia) albo
     odpowiedź za duża lub czytana za długo; skan przerwany (po 502/503/504 limiter
     sam wstrzymuje następne zapytanie)
  5  limiter: następne zapytanie wolno wysłać dopiero za dłużej niż {DEFAULT_MAX_WAIT:g} s;
     skan przerwany przed tym zapytaniem
  6  strony bez chunków /_next/static/chunks/*.js, chunk podany jako HTML albo więcej
     niż {MAX_CHUNKS} żądań chunków na skan (przerwany przed nadmiarowym żądaniem); także
     wynik niepełny z --compare (pierwszeństwo przed 0 i 7) albo z --baseline-out
     (baseline niezapisany): wynik i powody są wtedy wypisane
  7  --compare: są różnice względem pełnego wyniku (wynik wypisany, --baseline-out
     zapisany)

Komunikaty na stderr:
  Uwaga (niepełny wynik): …  w wyniku może brakować ścieżek /api i akcji: chunk
     pominięty (spoza allowlisty, bez treści albo status inny niż 200), brak lub
     nieczytelny runtime webpacka, różne build ID w trakcie skanu. Powody są też w
     polu "incomplete" (--json) i w nagłówku wyniku tekstowego. Bez --compare
     i --baseline-out kod wyjścia to wtedy 0.
  Info: …  bez wpływu na wynik: brak build ID, błąd odczytu lub zapisu cache.

Cache chunków: ${{XDG_CACHE_HOME:-~/.cache}}/deweloperuch-mcp/chunks/<ścieżka po
/_next/static/chunks/>. Plik w cache nie jest pobierany ponownie (nazwa zawiera hash
treści); chunki bez hasha w nazwie są pobierane przy każdym skanie.
"""


class ScanError(Exception):
    """Ends the run: the message goes to stderr, ``code`` becomes the exit code."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code


def _info(message: str) -> None:
    """A note that does not affect the result (``Info:``)."""
    print(f"Info: {message}", file=sys.stderr)


# --- allowlist and cache location -------------------------------------------------------


def is_chunk_path(path: str) -> bool:
    """A ``/_next/static/chunks/...js`` path: no query, no traversal, no odd escapes.

    The whole path must match ``CHUNK_RE`` (what the scanner finds in pages), its only
    percent escapes may be ``%5B``, ``%5D``, ``%28`` and ``%29`` (any case), and no
    segment may be empty, ``.`` or ``..``.
    """
    if not CHUNK_RE.fullmatch(path) or "%" in _ALLOWED_ESCAPE.sub("", path):
        return False
    return not any(segment in ("", ".", "..") for segment in path.split("/")[1:])


def is_scan_path(path: str) -> bool:
    """The scanner's allowlist: a page of ``PAGES`` or a chunk (``is_chunk_path``)."""
    return path in PAGES or is_chunk_path(path)


def default_cache_dir() -> Path:
    """``${XDG_CACHE_HOME:-~/.cache}/deweloperuch-mcp/chunks``, next to the limiter's lock."""
    return default_lock_dir() / "chunks"


def write_atomically(target: Path, data: bytes) -> None:
    """Write ``data`` so that readers see either the old ``target`` or the whole new one.

    A temporary file in the same directory, flushed to disk, then ``os.replace``; on any
    failure the temporary file is removed and the error raised.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp, target)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


# --- reading pages and chunks -----------------------------------------------------------


def build_id(html: str) -> str | None:
    """The build ID of the deployed site from a page's HTML; ``None`` if not found.

    App router: ``"b"`` of row 0 of the RSC payload in the page's ``self.__next_f``
    scripts (``0:{"P":null,"b":"<buildId>",…}``; a ``"b"`` anywhere else is data).
    Pages router: ``"buildId"`` of ``__NEXT_DATA__``. Anything but a plain token
    (letters, digits, ``_.-``, at most 100 characters) is ignored.
    """
    try:
        text = flight_from_html(html)
    except ValueError:  # a push chunk that is not a JSON string
        text = ""
    candidate: object = None
    row = _FLIGHT_ROW_0.search(text)
    if row is not None:
        try:
            head, _ = json.JSONDecoder().raw_decode(text, row.end())
        except (ValueError, RecursionError):
            head = None
        if isinstance(head, dict):
            candidate = head.get("b")
    if candidate is None:
        match = _NEXT_DATA_BUILD_ID.search(html)
        candidate = match.group(1) if match else None
    if isinstance(candidate, str) and _BUILD_ID.fullmatch(candidate):
        return candidate
    return None


def chunk_paths(html: str) -> set[str]:
    """Paths of the chunks a page references."""
    return set(CHUNK_RE.findall(html))


def js_object(src: str) -> dict[str, str]:
    """A minified object literal with numeric keys and string values (``{12:"a"}``).

    Raises ``ValueError`` for anything else.
    """
    data = json.loads(re.sub(r"([{,])(\d+):", r'\1"\2":', src))
    if not isinstance(data, dict) or not all(isinstance(v, str) for v in data.values()):
        raise ValueError(f"to nie jest mapa id -> nazwa: {src[:80]!r}")
    return {str(key): value for key, value in data.items()}


def lazy_chunks(runtime_js: str) -> set[str]:
    """Chunks the webpack runtime loads on demand.

    Raises ``ValueError`` when the runtime has no chunk map in the known format: the
    bundler or its output changed, and lazy chunks would otherwise be missed silently.
    """
    match = LAZY_NAMES_RE.search(runtime_js)
    if match is None:
        raise ValueError("Runtime webpacka nie zawiera mapy chunków w znanym formacie.")
    try:
        names, hashes = js_object(match.group(1)), js_object(match.group(2))
    except (ValueError, RecursionError) as err:
        raise ValueError(f"Nieczytelna mapa chunków w runtime webpacka ({err!r}).") from err
    out = {"/_next/" + path for path in LAZY_FIXED_RE.findall(runtime_js)}
    for chunk_id, digest in hashes.items():
        out.add(f"{CHUNKS_PREFIX}{names.get(chunk_id, chunk_id)}.{digest}.js")
    return out


def api_paths(js: str) -> set[str]:
    """Every ``/api/...`` string literal in client code, as written (query included)."""
    return set(API_RE.findall(js))


def server_actions(js: str) -> dict[str, str]:
    """Server Actions in client code: exported name -> action id."""
    return {name: action_id for action_id, name in ACTION_RE.findall(js)}


# --- fetching ---------------------------------------------------------------------------


class Scanner:
    """Fetches the pages and chunks of one scan: allowlist, limiter, STOP, chunk cache."""

    def __init__(
        self,
        fetch: Fetch,
        limiter: RequestLimiter,
        cache_dir: Path,
        now: Callable[[], float] = time.time,
    ) -> None:
        self._fetch = fetch
        self._limiter = limiter
        self._cache_dir = cache_dir
        self._now = now
        self._chunks: dict[str, str] = {}
        self.fetched = 0
        self.cached = 0
        self.requested = 0
        """Chunk requests sent in this scan, also those whose body was rejected."""
        self.incomplete: list[str] = []
        """Why the result may miss paths or actions; such a result is no baseline."""

    def warn_incomplete(self, message: str) -> None:
        """Record a reason why the result may be incomplete (``Uwaga (niepełny wynik):``)."""
        print(f"Uwaga (niepełny wynik): {message}", file=sys.stderr)
        self.incomplete.append(message)

    def needs_fetch(self, path: str) -> bool:
        """Whether ``chunk(path)`` would send a request (not read in this scan nor cached)."""
        return path not in self._chunks and not self._in_cache(path)

    def page(self, path: str) -> str:
        """The HTML of a page of ``PAGES``, always fetched (it names the current chunks)."""
        if path not in PAGES:
            raise ScanError(
                EXIT_USAGE, f"{path!r} nie jest na liście PAGES; zapytanie nie zostało wysłane."
            )
        return self._get(path).body.decode("utf-8", "replace")

    def chunk(self, path: str) -> str:
        """The text of a chunk: from this scan, from the cache, or fetched and cached."""
        if path in self._chunks:
            return self._chunks[path]
        if not is_chunk_path(path):
            raise ScanError(
                EXIT_USAGE,
                f"{path!r} jest spoza allowlisty chunków skanera; zapytanie nie zostało wysłane.",
            )
        body = self._from_cache(path)
        if body is not None:
            self.cached += 1
        else:
            if self.requested >= MAX_CHUNKS:  # hard limit, whatever the estimate said
                raise ScanError(
                    EXIT_DATA,
                    f"GET {path}: limit {MAX_CHUNKS} żądań chunków na skan wyczerpany "
                    "(pliki cache okazały się nieczytelne?). Skan przerwany przed tym "
                    "żądaniem; limitu nie podnoś bez decyzji (D2).",
                )
            self.requested += 1
            reply = self._get(path)
            if is_html(reply.headers, reply.body):
                raise ScanError(
                    EXIT_DATA,
                    f"GET {path}: oczekiwano JavaScriptu, a serwis zwrócił stronę HTML. "
                    "Skan przerwany.",
                )
            if reply.status != 200 or not reply.body:
                # Only a full 200 is a chunk: an empty or partial one would sit in the
                # cache for good under a name that is never fetched again.
                self.warn_incomplete(
                    f"GET {path}: HTTP {reply.status}, {len(reply.body)} B; chunk pominięty, "
                    "nie trafia do cache."
                )
                self._chunks[path] = ""
                return ""
            body = reply.body
            self.fetched += 1
            self._to_cache(path, body)
        text = body.decode("utf-8", "replace")
        self._chunks[path] = text
        return text

    def _get(self, path: str) -> Response:
        """One GET of an allowlisted path; anything but a usable 2xx ends the scan."""
        try:
            reply, note = get_once(
                BASE_URL + path,
                {"User-Agent": USER_AGENT},
                fetch=self._fetch,
                limiter=self._limiter,
                max_wait=DEFAULT_MAX_WAIT,
                now=self._now,
                source=STOP_SOURCE,
            )
        except NetworkError as err:
            raise ScanError(EXIT_HTTP, f"GET {path}: {err} Skan przerwany.") from err
        except StoppedError as err:
            raise ScanError(EXIT_STOP, f"{err} Skan przerwany przed GET {path}.") from err
        except WaitTooLongError as err:
            raise ScanError(EXIT_WAIT, f"{err} Skan przerwany przed GET {path}.") from err
        print(f"GET {path}: {status_line(reply)}", file=sys.stderr)
        if note:
            print(note, file=sys.stderr)
        try:
            check_reply(reply)
        except ReplyError as err:
            code = EXIT_STOP if err.kind == "stop" else EXIT_HTTP
            hint = ""
            if err.kind == "redirect":
                hint = (
                    " Skaner nie podąża za przekierowaniami; jeśli strona się przeniosła, "
                    "zaktualizuj PAGES w recon/scan_bundles.py."
                )
            raise ScanError(code, f"GET {path}: {err}{hint} Skan przerwany.") from err
        return reply

    def _cache_file(self, path: str) -> Path:
        # is_chunk_path() has ruled out empty, "." and ".." segments.
        return self._cache_dir.joinpath(*path[len(CHUNKS_PREFIX) :].split("/"))

    def _in_cache(self, path: str) -> bool:
        if not _HASHED_NAME.search(path.rsplit("/", 1)[-1]):
            return False  # without a content hash the name does not pin the content
        try:
            info = self._cache_file(path).stat()
        except OSError:
            return False
        return stat.S_ISREG(info.st_mode) and info.st_size > 0

    def _from_cache(self, path: str) -> bytes | None:
        if not _HASHED_NAME.search(path.rsplit("/", 1)[-1]):
            return None
        target = self._cache_file(path)
        try:
            body = target.read_bytes()
        except FileNotFoundError:
            return None
        except OSError as err:
            _info(f"nie można odczytać {target} z cache ({err}); pobieram chunk.")
            return None
        return body or None  # an empty file is no chunk: fetch it again

    def _to_cache(self, path: str, body: bytes) -> None:
        try:
            write_atomically(self._cache_file(path), body)
        except OSError as err:
            _info(f"nie zapisano {path} w cache ({err}).")


# --- the scan ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScanResult:
    """What ``--json`` prints, in this order."""

    build_id: str | None
    pages: int
    chunks: int
    chunks_fetched: int
    chunks_cached: int
    api: list[str]  # sorted
    actions: dict[str, str]  # name -> id, sorted by name
    incomplete: list[str]  # why the result may be incomplete; empty when it is complete


@dataclass(frozen=True)
class Baseline:
    """What drift is measured on: ``/api`` paths and action names, without ids."""

    api: frozenset[str]
    actions: frozenset[str]

    def to_json(self) -> dict[str, list[str]]:
        return {"api": sorted(self.api), "actions": sorted(self.actions)}


def _allowed_chunks(scanner: Scanner, paths: Iterable[str]) -> set[str]:
    found = set(paths)
    allowed = {path for path in found if is_chunk_path(path)}
    for path in sorted(found - allowed):
        scanner.warn_incomplete(f"pomijam {path!r}: ścieżka spoza allowlisty chunków skanera.")
    return allowed


def _check_chunk_limit(scanner: Scanner, chunks: Iterable[str]) -> None:
    """Stop before fetching more chunks than ``MAX_CHUNKS`` in this scan.

    An estimate: a cached file that cannot be read is fetched after all, which
    ``Scanner.chunk`` still keeps within the limit.
    """
    needed = scanner.requested + sum(1 for path in chunks if scanner.needs_fetch(path))
    if needed > MAX_CHUNKS:
        raise ScanError(
            EXIT_DATA,
            f"Skan wymagałby pobrania {needed} chunków (limit {MAX_CHUNKS} na skan, serwis "
            "ma ich ok. 115). Przerwany przed ich pobraniem: sprawdź strony i mapę chunków "
            "runtime'u webpacka; limitu nie podnoś bez decyzji (D2).",
        )


def scan(scanner: Scanner) -> ScanResult:
    """Pages first, then the webpack runtime and its lazy chunks, then all chunks."""
    chunks: set[str] = set()
    builds: list[str] = []
    for page in PAGES:
        html = scanner.page(page)
        found = build_id(html)
        if found is not None and found not in builds:
            builds.append(found)
        chunks |= chunk_paths(html)
    if not chunks:
        raise ScanError(
            EXIT_DATA,
            "Żadna strona nie odwołuje się do /_next/static/chunks/*.js: zmienił się format "
            "stron albo serwis odpowiada skanerowi inaczej niż przeglądarce. Skan przerwany.",
        )
    if not builds:
        _info("nie znaleziono build ID w HTML stron (zmiana formatu Next.js?).")
    elif len(builds) > 1:
        scanner.warn_incomplete(
            f"strony podały różne build ID ({', '.join(builds)}): deploy w trakcie skanu? "
            "Powtórz skan."
        )
    chunks = _allowed_chunks(scanner, chunks)
    _check_chunk_limit(scanner, chunks)  # before the first chunk request

    runtime = next((path for path in sorted(chunks) if "/webpack-" in path), None)
    if runtime is None:
        scanner.warn_incomplete(
            "nie znaleziono runtime'u webpacka (/_next/static/chunks/webpack-*.js): leniwe "
            "chunki pominięte."
        )
    else:
        try:
            lazy = lazy_chunks(scanner.chunk(runtime))
        except ValueError as err:
            scanner.warn_incomplete(f"{err} Leniwe chunki pominięte.")
        else:
            chunks |= _allowed_chunks(scanner, lazy)
            _check_chunk_limit(scanner, chunks)  # the lazy map is known only now

    api: set[str] = set()
    actions: dict[str, str] = {}
    for path in sorted(chunks):
        js = scanner.chunk(path)
        api |= api_paths(js)
        actions.update(server_actions(js))
    return ScanResult(
        build_id=builds[0] if builds else None,
        pages=len(PAGES),
        chunks=len(chunks),
        chunks_fetched=scanner.fetched,
        chunks_cached=scanner.cached,
        api=sorted(api),
        actions=dict(sorted(actions.items())),
        incomplete=list(scanner.incomplete),
    )


def baseline_of(result: ScanResult) -> Baseline:
    return Baseline(frozenset(result.api), frozenset(result.actions))


def _strings(value: object) -> TypeGuard[list[str]]:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def load_baseline(path: Path) -> Baseline:
    """``{"api": [paths], "actions": [names]}``; ``actions`` may also be ``{name: id}``
    (the ``--json`` output), the ids are ignored. Other keys are ignored too."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as err:
        raise ScanError(
            EXIT_USAGE,
            f"Brak pliku baseline {path}. Pierwszy baseline zapisz przez --baseline-out. "
            "Skan się nie zaczął.",
        ) from err
    except (OSError, ValueError, RecursionError) as err:  # UnicodeDecodeError is a ValueError
        raise ScanError(
            EXIT_USAGE, f"Nie da się odczytać baseline {path}: {err}. Skan się nie zaczął."
        ) from err
    api = data.get("api") if isinstance(data, dict) else None
    actions = data.get("actions") if isinstance(data, dict) else None
    if isinstance(actions, dict) and all(isinstance(value, str) for value in actions.values()):
        actions = list(actions)
    if not (_strings(api) and _strings(actions)):
        raise ScanError(
            EXIT_USAGE,
            f'Baseline {path} ma zły format: oczekiwano {{"api": [ścieżki], "actions": '
            "[nazwy akcji]}. Skan się nie zaczął.",
        )
    return Baseline(frozenset(api), frozenset(actions))


def compare(current: Baseline, previous: Baseline) -> dict[str, list[str]]:
    """New and removed ``/api`` paths and action names, sorted."""
    return {
        "api_added": sorted(current.api - previous.api),
        "api_removed": sorted(previous.api - current.api),
        "actions_added": sorted(current.actions - previous.actions),
        "actions_removed": sorted(previous.actions - current.actions),
    }


# --- output and command line --------------------------------------------------------


def _print_text(result: ScanResult, drift: dict[str, list[str]] | None, baseline: Path) -> None:
    print(f"# build ID: {result.build_id or 'nieznany'}")
    print(
        f"# strony: {result.pages}, chunki: {result.chunks} "
        f"(pobrane: {result.chunks_fetched}, z cache: {result.chunks_cached})"
    )
    if result.incomplete:
        print("# NIEPEŁNY WYNIK (porównanie tylko orientacyjne, bez nowego baseline):")
        for reason in result.incomplete:
            print(f"#   - {reason}")
    print("\n## ścieżki /api")
    for path in result.api:
        print(f"  {path}")
    print("\n## server actions")
    for name, action_id in result.actions.items():
        print(f"  {name:32} {action_id}")
    if drift is None:
        return
    print(f"\n## porównanie z baseline {baseline}")
    if not any(drift.values()):
        print("  brak różnic")
        return
    for title, kind in (("ścieżki /api", "api"), ("server actions (nazwy)", "actions")):
        print(f"  {title}:")
        for item in drift[f"{kind}_added"]:
            print(f"    + {item}")
        for item in drift[f"{kind}_removed"]:
            print(f"    - {item}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python3 recon/scan_bundles.py",
        description="Skan bundli JS deweloperuch.pl: build ID, ścieżki /api/* i server "
        "actions, do wykrywania zmian po deployu serwisu (D7). Każde zapytanie przechodzi "
        "przez wspólny limiter (1 zapytanie/s); skaner pobiera tylko strony z listy PAGES "
        "i chunki /_next/static/chunks/*.js (ok. 140 zapytań przy pustym cache). Żywe "
        "uruchomienie wymaga zgody użytkownika (D9).",
        epilog=EXIT_CODES_HELP,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="wynik jako JSON: build_id, pages, chunks, chunks_fetched, chunks_cached, api "
        "(posortowane), actions (nazwa -> id), incomplete (powody niepełnego wyniku, pusta "
        "lista przy pełnym); z --compare także drift",
    )
    parser.add_argument(
        "--compare",
        type=Path,
        metavar="PLIK",
        help='porównaj z baseline {"api": [...], "actions": [nazwy]}: nowe i usunięte '
        "ścieżki /api i nazwy akcji (ID akcji i build ID się nie liczą); różnice: kod 7",
    )
    parser.add_argument(
        "--baseline-out",
        type=Path,
        metavar="PLIK",
        help="po udanym skanie zapisz baseline (posortowane api i nazwy akcji) do PLIK, "
        "atomowo; istniejący plik zostaje zastąpiony",
    )
    return parser


def main(
    argv: list[str] | None = None,
    *,
    fetch: Fetch = urllib_fetch,
    limiter: RequestLimiter | None = None,
    cache_dir: Path | None = None,
    clock: Callable[[], float] = time.time,
) -> int:
    """Run the scan; returns the exit code. Keyword arguments exist for tests."""
    args = build_parser().parse_args(argv)
    drift: dict[str, list[str]] | None = None
    try:
        # Everything that can fail without the service fails before the first request.
        previous = None if args.compare is None else load_baseline(args.compare)
        if args.baseline_out is not None:
            _check_baseline_out(args.baseline_out)
        scanner = Scanner(
            fetch,
            limiter or RequestLimiter(),
            default_cache_dir() if cache_dir is None else cache_dir,
            clock,
        )
        result = scan(scanner)
        current = baseline_of(result)
        if previous is not None:
            drift = compare(current, previous)
        if args.json:
            output: dict[str, Any] = dataclasses.asdict(result)
            if drift is not None:
                output["drift"] = drift
            print(json.dumps(output, indent=2, ensure_ascii=False))
        else:
            _print_text(result, drift, args.compare)
        if args.baseline_out is not None:
            if result.incomplete:
                raise ScanError(
                    EXIT_DATA,
                    "Wynik skanu może być niepełny (ostrzeżenia „Uwaga (niepełny wynik)” "
                    f"wyżej), więc baseline {args.baseline_out} nie został zapisany. Usuń "
                    "przyczynę i powtórz skan.",
                )
            text = json.dumps(current.to_json(), indent=2, ensure_ascii=False) + "\n"
            try:
                write_atomically(args.baseline_out, text.encode("utf-8"))
            except OSError as err:
                raise ScanError(
                    EXIT_USAGE, f"Nie udało się zapisać baseline {args.baseline_out}: {err}"
                ) from err
            print(f"Zapisano baseline {args.baseline_out}", file=sys.stderr)
        if drift is not None and result.incomplete:
            raise ScanError(
                EXIT_DATA,
                "Wynik skanu może być niepełny (ostrzeżenia „Uwaga (niepełny wynik)” wyżej): "
                "różnice względem baseline są tylko orientacyjne, nie traktuj ich jako dryfu. "
                "Usuń przyczynę i powtórz skan.",
            )
    except ScanError as err:
        print(err, file=sys.stderr)
        return err.code
    return EXIT_DRIFT if drift is not None and any(drift.values()) else EXIT_OK


def _check_baseline_out(target: Path) -> None:
    """``--baseline-out`` must name a file in an existing directory."""
    if target.is_dir():
        raise ScanError(
            EXIT_USAGE,
            f"--baseline-out {target} to katalog; podaj ścieżkę pliku, np. "
            f"{target / 'scan.json'}. Skan się nie zaczął.",
        )
    if not target.parent.is_dir():
        raise ScanError(
            EXIT_USAGE, f"Brak katalogu {target.parent} dla --baseline-out. Skan się nie zaczął."
        )


if __name__ == "__main__":
    sys.exit(main())
