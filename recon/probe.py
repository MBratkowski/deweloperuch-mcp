"""One read-only verification request to deweloperuch.pl (stdlib only).

The only way recon-verifier sends live requests (CLAUDE.md, D9). One run sends at most
one GET, inside the shared limiter slot (D2), with the one User-Agent (D9)::

    python3 recon/probe.py api "/api/city-lookup?city=warszawa"
    python3 recon/probe.py page "/ceny-ofertowe/warszawa/mieszkania?perPage=10" --prop initialData
    python3 recon/probe.py api "/api/offer-count?city=warszawa" --save offer_count.v2

- Paths only, never URLs, and only those on the read allowlist (recon/allowlist.py).
- No retries, no redirects. 401, 403, 429 and Cloudflare challenges stop the series
  (exit code 3). A 429 pauses the shared limiter for at least ``PAUSE_AFTER_429``,
  a 502/503/504 for ``Retry-After`` or ``PAUSE_AFTER_5XX``.
- Bodies over ``MAX_BODY_BYTES`` or slower than ``BODY_DEADLINE`` are refused (exit
  code 4): probe is not a tool for dumps (D5).
- Values of personal-data keys (``REDACTED_KEYS``) are replaced on stdout and in samples.
- ``--save`` writes a trimmed sample to docs/discovery/samples/ in the format of the
  existing ones and never overwrites a file.

Exit codes: ``EXIT_CODES_HELP`` (also in ``--help``).

The transport and the checks are shared with recon/scan_bundles.py (recon/http_common.py);
the response policy (STOP, pauses, body limit) with the package's client
(``deweloperuch_mcp.http_policy``, through config).

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
    WaitTooLongError,
    is_html,
    with_rsc_token,
)

# Explicit re-exports (`X as X`): probe's documented limits and transport, used by its
# docstring and its tests as probe.<name>.
from config import MAX_BODY_BYTES as MAX_BODY_BYTES
from config import PAUSE_AFTER_5XX as PAUSE_AFTER_5XX
from config import PAUSE_AFTER_429 as PAUSE_AFTER_429
from config import body_length as body_length

# isort: split
import argparse
import json
import math
import re
import sys
import time
import urllib.parse
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from allowlist import PAGE_ROUTES, match_api, match_excluded_api, match_page
from flight import component_props, find_json_after, flight_from_html
from http_common import BODY_DEADLINE as BODY_DEADLINE
from http_common import TIMEOUT as TIMEOUT
from http_common import (
    Fetch,
    NetworkError,
    ReplyError,
    check_reply,
    excerpt,
    get_once,
    status_line,
)
from http_common import Response as Response
from http_common import read_body as read_body
from http_common import urllib_fetch as urllib_fetch

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "docs" / "discovery" / "samples"

STDOUT_TRIM = 3
"""Default ``--trim``: list items shown on stdout."""

SAMPLE_ITEMS = 3
"""Sample convention: a list keeps 3 items."""

SAMPLE_MAP_THRESHOLD = 40
SAMPLE_KEYS = 2
"""Sample convention: a map keyed by numeric ids with more than 40 keys keeps 2 of them
(e.g. api.inv_sale_events.json, 16 keys, stays whole). Applies on stdout too."""

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_STOP = 3
EXIT_HTTP = 4
EXIT_WAIT = 5
EXIT_DATA = 6

EXIT_CODES_HELP = """\
kody wyjścia:
  0  sukces
  2  błąd użycia: pełny URL zamiast ścieżki, ścieżka spoza allowlisty, zła opcja
     albo nazwa --save, próbka już istnieje; zapytanie nie zostało wysłane (wyjątek:
     plik próbki powstał w trakcie zapytania albo zapis próbki się nie udał)
  3  STOP: 401, 403, 429 albo challenge Cloudflare (captcha, WAF); przerwij serię
     zapytań i zgłoś to użytkownikowi, niczego nie ponawiaj (po 429 limiter wstrzymuje
     następne zapytanie co najmniej na 60 s)
  4  inny błąd HTTP (3xx, pozostałe 4xx, 5xx), sieci (timeout, brak połączenia)
     albo odpowiedź za duża (zrzut, D5) lub czytana za długo; po 5xx odczekaj przed
     ponowieniem (po 502/503/504 limiter sam wstrzymuje następne zapytanie)
  5  limiter: następne zapytanie wolno wysłać dopiero za dłużej niż --max-wait;
     zapytanie nie zostało wysłane
  6  odpowiedź 2xx bez oczekiwanych danych (nie JSON, brak propsa z --prop, dane
     zagnieżdżone zbyt głęboko)
"""

REDACTED = "[usunięte]"
# Keys whose values may hold personal data, compared case-insensitively at every level.
# `additionalInfo` is free text: reports on the abuse map, remarks in RCN records.
REDACTED_KEYS = frozenset(
    {"additionalinfo", "email", "e-mail", "phone", "phonenumber", "telefon", "telephone"}
)

_SAVE_NAME = re.compile(r"[a-z0-9_]+(?:\.[a-z0-9_]+)?")
_PROP_NAME = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*")
_SCHEME = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*:")
# RFC 3986 path characters without percent-encoding: documented paths are plain slugs.
_PATH_CHARS = re.compile(r"[A-Za-z0-9._~!$&'()*+,;=:@/-]*")
_CONTROL_OR_BACKSLASH = re.compile(r"[\x00-\x1f\x7f\\]")
_LONE_PERCENT = re.compile(r"%(?![0-9A-Fa-f]{2})")
_QUERY_SAFE = "=&%+,:;@!$'()*/?~"  # kept as typed; everything else is percent-encoded
_NUMERIC_KEY = re.compile(r"[0-9]+")


class ProbeError(Exception):
    """Ends the run: the message goes to stderr, ``code`` becomes the exit code."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class Plan:
    """A checked request, ready to send."""

    mode: str  # "api" | "page"
    path: str  # as given, without host: goes into the sample's `_request`
    url: str
    headers: dict[str, str]
    prop: str | None
    save_to: Path | None


# --- checking the input --------------------------------------------------------------


def _usage(message: str) -> ProbeError:
    return ProbeError(EXIT_USAGE, message)


def split_path(text: str) -> tuple[str, str]:
    """``(path, query)`` of a service-relative path; anything else is a usage error."""
    if _SCHEME.match(text):
        raise _usage(
            "Podaj samą ścieżkę zaczynającą się od /, nie pełny URL "
            "(np. /api/cities?q=krak). Host jest stały: deweloperuch.pl."
        )
    if text.startswith("//"):
        raise _usage("Ścieżka zaczynająca się od // wskazuje inny host. Podaj np. /api/cities.")
    if not text.startswith("/"):
        raise _usage("Ścieżka musi zaczynać się od / i nie zawierać hosta, np. /api/cities?q=krak.")
    if _CONTROL_OR_BACKSLASH.search(text):
        raise _usage("Ścieżka zawiera niedozwolone znaki (sterujące albo \\).")
    if "#" in text:
        raise _usage("Bez #fragmentu: serwer go nie dostaje. Usuń część od #.")
    path, _, query = text.partition("?")
    if not _PATH_CHARS.fullmatch(path):
        raise _usage(
            "Ścieżka (część przed ?) może zawierać tylko znaki ASCII dozwolone w adresie, "
            "bez kodowania %: udokumentowane trasy to zwykłe slugi."
        )
    if any(segment in ("", ".", "..") for segment in path.split("/")[1:]):
        raise _usage("Ścieżka nie może zawierać pustych segmentów (//) ani segmentów . i ..")
    return path, query


def _check_api(path: str) -> None:
    if not path.startswith("/api/"):
        raise _usage("Tryb api przyjmuje tylko ścieżki /api/...; strony pobiera tryb page.")
    excluded = match_excluded_api(path)
    if excluded is not None:
        raise _usage(f"{excluded} jest poza zakresem projektu (CLAUDE.md); probe go nie wywołuje.")
    if match_api(path) is None:
        raise _usage(
            f"{path} jest spoza allowlisty odczytu (docs/discovery/endpoints.md). Nowy endpoint "
            "trzeba najpierw opisać w dokumentacji i dopisać do recon/allowlist.py."
        )


def _check_page(path: str, query: str) -> None:
    if path == "/api" or path.startswith("/api/"):
        raise _usage("To endpoint JSON: użyj trybu api.")
    if match_page(path) is None:
        routes = "\n  ".join(PAGE_ROUTES)
        raise _usage(
            f"{path} jest spoza allowlisty stron (docs/discovery/pages-rsc.md). "
            f"Dozwolone trasy:\n  {routes}"
        )
    # Decoded first: `%5Frsc=x` and `_rsc%3Dx` reach the server as `_rsc` too.
    if any(urllib.parse.unquote_plus(item).split("=", 1)[0] == "_rsc" for item in query.split("&")):
        raise _usage("Nie podawaj _rsc: probe dokłada go sam (deterministyczny token).")


def encode_query(query: str) -> str:
    """Percent-encode what may not travel raw (spaces, non-ASCII, a lone %); keep escapes."""
    return urllib.parse.quote(_LONE_PERCENT.sub("%25", query), safe=_QUERY_SAFE)


def _sample_path(mode: str, name: str, prop: str | None, samples_dir: Path) -> Path:
    if not _SAVE_NAME.fullmatch(name):
        raise _usage(
            "Nazwa --save to nazwa[.wariant] z małych liter, cyfr i _, "
            "np. city_lookup albo offers_list.filtered."
        )
    if mode == "page" and prop is None:
        raise _usage("--save w trybie page wymaga --prop: próbka strony to wartość jednego propsa.")
    if not samples_dir.is_dir():
        raise _usage(f"Brak katalogu próbek {samples_dir}.")
    target = samples_dir / f"{mode}.{name}.json"
    if target.exists():
        raise _usage(
            f"Próbka {target.name} już istnieje i nie zostanie nadpisana. Zapisz nową "
            f"obserwację jako wariant, np. --save {name.split('.')[0]}.v2."
        )
    return target


def make_plan(
    mode: str, raw_path: str, prop: str | None, save: str | None, samples_dir: Path
) -> Plan:
    """Check everything that can be checked before sending anything."""
    given = raw_path.strip()
    path, query = split_path(given)
    if mode == "api":
        _check_api(path)
    else:
        _check_page(path, query)
    if prop is not None and not _PROP_NAME.fullmatch(prop):
        raise _usage(f"--prop to nazwa propsa komponentu (identyfikator JS), podano {prop!r}.")
    save_to = None if save is None else _sample_path(mode, save, prop, samples_dir)

    target = f"{path}?{encode_query(query)}" if query else path
    headers = {"User-Agent": USER_AGENT}
    if mode == "api":
        headers["Accept"] = "application/json"
    else:
        headers["RSC"] = "1"
        # The same deterministic token as the package's RSC adapter (deweloperuch_mcp.flight).
        target = with_rsc_token(target)
    return Plan(mode, given, BASE_URL + target, headers, prop, save_to)


# --- sending ---------------------------------------------------------------------------


def send(
    plan: Plan, fetch: Fetch, limiter: RequestLimiter, max_wait: float, now: Callable[[], float]
) -> tuple[Response, str | None]:
    """The one request, inside the limiter slot; ``Retry-After`` recorded before leaving it."""
    try:
        return get_once(
            plan.url, plan.headers, fetch=fetch, limiter=limiter, max_wait=max_wait, now=now
        )
    except NetworkError as err:
        raise ProbeError(EXIT_HTTP, str(err)) from err
    except WaitTooLongError as err:
        raise ProbeError(EXIT_WAIT, f"{err} Probe nie wysłał zapytania.") from err


# --- reading the response ------------------------------------------------------------


def check_status(reply: Response) -> None:
    """Raise for anything but a usable 2xx; never retry."""
    try:
        check_reply(reply)
    except ReplyError as err:
        if err.kind == "stop":
            raise ProbeError(EXIT_STOP, str(err)) from err
        hint = ""
        if err.kind == "redirect":
            hint = (
                " Probe nie podąża za przekierowaniami; jeśli cel jest na allowliście, "
                "podaj go wprost."
            )
        raise ProbeError(EXIT_HTTP, f"{err}{hint}") from err


def _flight_text(reply: Response) -> str:
    text = reply.body.decode("utf-8", "replace")
    if is_html(reply.headers, reply.body):
        print(
            "Uwaga: serwis zwrócił HTML zamiast RSC (text/x-component); "
            "dane odczytane ze skryptów self.__next_f strony.",
            file=sys.stderr,
        )
        return flight_from_html(text)
    return text


def data_props(text: str) -> list[dict[str, Any]]:
    """Client component props holding data (objects, arrays): name, JSON type, size."""
    found: list[dict[str, Any]] = []
    for name, value in component_props(text):
        if isinstance(value, dict | list):
            kind = "object" if isinstance(value, dict) else "array"
            entry = {"name": name, "type": kind, "size": len(value)}
            if entry not in found:
                found.append(entry)
    return found


def extract(plan: Plan, reply: Response) -> Any:
    """The data of a 2xx response: the JSON body (api) or the value of ``--prop`` (page)."""
    if plan.mode == "api":
        if is_html(reply.headers, reply.body):
            raise ProbeError(EXIT_DATA, "Oczekiwano JSON, a serwis zwrócił stronę HTML.")
        try:
            return json.loads(reply.body)
        except ValueError as err:
            raise ProbeError(
                EXIT_DATA, f"Odpowiedź nie jest JSON-em ({err}). Początek: {excerpt(reply.body)}"
            ) from err
    assert plan.prop is not None
    text = _flight_text(reply)
    hits = find_json_after(text, plan.prop)
    if not hits:
        names = ", ".join(dict.fromkeys(entry["name"] for entry in data_props(text))) or "brak"
        raise ProbeError(
            EXIT_DATA, f"Nie znaleziono propsa {plan.prop!r}. Propsy z danymi na stronie: {names}."
        )
    if len(hits) > 1:
        print(
            f"Prop {plan.prop!r} występuje {len(hits)} razy; pokazuję pierwsze wystąpienie.",
            file=sys.stderr,
        )
    return hits[0]


# --- trimming, redaction, samples ----------------------------------------------------


def redact(value: Any) -> Any:
    """Replace values of ``REDACTED_KEYS`` at every level; empty ones (null, "") stay."""
    if isinstance(value, dict):
        return {
            key: REDACTED
            if key.lower() in REDACTED_KEYS and item not in (None, "")
            else redact(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def trim(value: Any, items: int) -> Any:
    """Shorten for reading, the way the existing samples were shortened.

    A list longer than ``items`` keeps its first ``items`` elements plus
    ``"... (N more, M total)"``. A map whose keys are all numeric ids (e.g. sale id ->
    events) with more than ``SAMPLE_MAP_THRESHOLD`` entries keeps its first
    ``SAMPLE_KEYS`` plus ``"...": "N more keys"``; smaller maps stay whole.
    """
    if isinstance(value, list):
        kept = [trim(item, items) for item in value[:items]]
        if len(value) > items:
            kept.append(f"... ({len(value) - items} more, {len(value)} total)")
        return kept
    if isinstance(value, dict):
        if len(value) > SAMPLE_MAP_THRESHOLD and all(_NUMERIC_KEY.fullmatch(k) for k in value):
            shortened = {key: trim(value[key], items) for key in list(value)[:SAMPLE_KEYS]}
            shortened["..."] = f"{len(value) - SAMPLE_KEYS} more keys"
            return shortened
        return {key: trim(item, items) for key, item in value.items()}
    return value


def save_sample(plan: Plan, value: Any, today: date) -> None:
    """Write the sample envelope; an existing file is never overwritten."""
    target = plan.save_to
    assert target is not None
    sample = trim(redact(value), SAMPLE_ITEMS)
    envelope: dict[str, Any]
    if plan.mode == "api":
        envelope = {"_request": f"GET {plan.path}", "_captured": today.isoformat()}
        envelope["response"] = sample
    else:
        envelope = {"_request": f"GET {plan.path} (RSC)", "_prop": plan.prop}
        envelope.update({"_captured": today.isoformat(), "value": sample})
    text = json.dumps(envelope, indent=2, ensure_ascii=False)  # before the file exists
    created = False
    try:
        with open(target, "x", encoding="utf-8") as out:
            created = True
            out.write(text)
    except FileExistsError as err:
        raise _usage(
            f"Próbka {target.name} powstała w trakcie zapytania i nie zostanie "
            "nadpisana. Zapisz obserwację jako inny wariant."
        ) from err
    except OSError as err:
        if created:  # a partial file of this run, never someone else's
            target.unlink(missing_ok=True)
        raise _usage(f"Nie udało się zapisać próbki {target}: {err}") from err
    print(f"Zapisano próbkę {target}", file=sys.stderr)


def _print_json(value: Any) -> None:
    print(json.dumps(value, indent=2, ensure_ascii=False))


# --- command line --------------------------------------------------------------------


def _seconds(text: str) -> float:
    try:
        value = float(text)
    except ValueError:
        value = math.nan
    if not math.isfinite(value) or value < 0:
        raise argparse.ArgumentTypeError(f"oczekiwano liczby sekund >= 0, podano {text!r}")
    return value


def _count(text: str) -> int:
    try:
        value = int(text)
    except ValueError:
        value = -1
    if value < 0:
        raise argparse.ArgumentTypeError(f"oczekiwano liczby całkowitej >= 0, podano {text!r}")
    return value


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--save",
        metavar="NAZWA[.WARIANT]",
        help="zapisz próbkę docs/discovery/samples/<tryb>.NAZWA[.WARIANT].json "
        "(przycięta, bez danych osobowych; istniejący plik nie zostanie nadpisany)",
    )
    common.add_argument(
        "--max-wait",
        type=_seconds,
        default=DEFAULT_MAX_WAIT,
        metavar="SEKUNDY",
        help="najdłuższe czekanie na swoją kolej w limiterze, skończona liczba sekund "
        "(domyślnie %(default)g s)",
    )
    output = common.add_mutually_exclusive_group()
    output.add_argument(
        "--trim",
        type=_count,
        default=STDOUT_TRIM,
        metavar="N",
        help="na stdout przytnij tablice do N elementów (domyślnie %(default)s; próbka z "
        "--save ma zawsze 3). Mapy id -> wartość powyżej 40 kluczy są zawsze skracane "
        "do 2 kluczy, jak w próbkach",
    )
    output.add_argument(
        "--full",
        action="store_true",
        help="stdout bez przycinania (dane osobowe i tak są usuwane)",
    )

    formatter = argparse.RawDescriptionHelpFormatter
    parser = argparse.ArgumentParser(
        prog="python3 recon/probe.py",
        description="Pojedyncze zapytanie weryfikacyjne (GET) do deweloperuch.pl przez "
        "wspólny limiter (1 zapytanie/s). Przyjmuje ścieżki z allowlisty odczytu, "
        "nigdy pełne URL-e.",
        epilog=EXIT_CODES_HELP,
        formatter_class=formatter,
    )
    modes = parser.add_subparsers(dest="mode", required=True, metavar="{api,page}")
    api = modes.add_parser(
        "api",
        parents=[common],
        help="GET /api/... z docs/discovery/endpoints.md, wynik JSON",
        description="GET endpointu JSON z docs/discovery/endpoints.md.",
        epilog=EXIT_CODES_HELP,
        formatter_class=formatter,
    )
    api.add_argument("path", metavar="ŚCIEŻKA", help='np. "/api/cities?q=krak&limit=8"')
    api.set_defaults(prop=None)
    page = modes.add_parser(
        "page",
        parents=[common],
        help="GET strony z docs/discovery/pages-rsc.md jako RSC",
        description="GET strony jako RSC (nagłówek RSC: 1, deterministyczny _rsc). Bez "
        "--prop wypisuje propsy z danymi (nazwa, typ, rozmiar).",
        epilog=EXIT_CODES_HELP,
        formatter_class=formatter,
    )
    page.add_argument("path", metavar="ŚCIEŻKA", help='np. "/ceny-ofertowe/warszawa/mieszkania"')
    page.add_argument(
        "--prop", metavar="NAZWA", help="wypisz wartość propsa (pierwsze wystąpienie)"
    )
    return parser


def main(
    argv: list[str] | None = None,
    *,
    fetch: Fetch = urllib_fetch,
    limiter: RequestLimiter | None = None,
    samples_dir: Path = SAMPLES_DIR,
    today: date | None = None,
    clock: Callable[[], float] = time.time,
) -> int:
    """Run probe; returns the exit code. Keyword arguments exist for tests."""
    args = build_parser().parse_args(argv)
    try:
        plan = make_plan(args.mode, args.path, args.prop, args.save, samples_dir)
        reply, note = send(plan, fetch, limiter or RequestLimiter(), args.max_wait, clock)
        print(status_line(reply), file=sys.stderr)
        if note:
            print(note, file=sys.stderr)
        check_status(reply)
        try:
            if plan.mode == "page" and plan.prop is None:
                _print_json(data_props(_flight_text(reply)))
                return EXIT_OK
            value = extract(plan, reply)
            shown = redact(value)
            _print_json(shown if args.full else trim(shown, args.trim))
            if plan.save_to is not None:
                save_sample(plan, value, today or date.today())
        except RecursionError as err:
            raise ProbeError(
                EXIT_DATA, "Dane odpowiedzi są zagnieżdżone zbyt głęboko, by je przetworzyć."
            ) from err
    except ProbeError as err:
        print(err, file=sys.stderr)
        return err.code
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
