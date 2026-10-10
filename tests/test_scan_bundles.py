"""recon/scan_bundles.py: drift scan through the shared limiter, on a mocked transport.

Nothing here reaches the network: requests go to ``FakeSite`` (injected ``fetch``), the
limiter and the chunk cache live in temporary directories. Pages, chunks and the webpack
runtime are small synthetic fixtures in the formats the scanner parses.
"""

import ast
import fcntl
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

import http_common
import scan_bundles
from deweloperuch_mcp import identity
from deweloperuch_mcp.throttle import LOCK_FILENAME, RequestLimiter
from http_common import Response

REPO = Path(__file__).resolve().parent.parent
SCANNER = REPO / "recon" / "scan_bundles.py"

USAGE, STOP, HTTP_ERROR, WAIT, NO_DATA, DRIFT = 2, 3, 4, 5, 6, 7

# --- fixtures: a tiny Next.js site -----------------------------------------------------

CHUNKS = "/_next/static/chunks/"
RUNTIME = CHUNKS + "webpack-0123456789abcdef.js"
MAIN = CHUNKS + "main-app-89abcdef01234567.js"
PAGE_CHUNK = CHUNKS + "app/ceny-ofertowe/%5Bcity%5D/mieszkania/page-fedcba9876543210.js"
LAZY_NAMED = CHUNKS + "vendors.aaaa1111bbbb2222.js"
LAZY_BY_ID = CHUNKS + "789.eeee5555ffff6666.js"
LAZY_FIXED = CHUNKS + "framework-0011223344556677.js"

VALUATION_ID = "7f" + "a1" * 20
INVEST_ID = "40" + "b2" * 20

# The shape of webpack's chunk-file function (`r.u`) as LAZY_NAMES_RE expects it.
RUNTIME_JS = (
    '(()=>{var r={};r.u=e=>"static/chunks/"+(({123:"vendors"})[e]||e)+"."+'
    '({123:"aaaa1111bbbb2222",789:"eeee5555ffff6666"})[e]+".js",r.p="/_next/";'
    'var f="static/chunks/framework-0011223344556677.js";})();'
)


def action(action_id: str, name: str) -> str:
    """A minified ``createServerReference`` call as Next.js emits it."""
    return (
        f'(0,n.createServerReference)("{action_id}",n.callServer,void 0,'
        f'n.findSourceMapURL,"{name}")'
    )


CHUNK_JS = {
    RUNTIME: RUNTIME_JS,
    MAIN: 'fetch("/api/cities?q="+e);fetch(`/api/investments/${t}/sale-events`);',
    PAGE_CHUNK: (
        f"let a={action(VALUATION_ID, 'fetchStandaloneValuation')};"
        'fetch("/api/offer-count?city="+c);'
    ),
    LAZY_NAMED: "fetch('/api/map/investments')",
    LAZY_BY_ID: f"let b={action(INVEST_ID, 'createInvestmentAction')};",
    LAZY_FIXED: "var x=1;",
}

EXPECTED_API = [
    "/api/cities?q=",
    "/api/investments/${t}/sale-events",
    "/api/map/investments",
    "/api/offer-count?city=",
]
EXPECTED_ACTIONS = {
    "createInvestmentAction": INVEST_ID,
    "fetchStandaloneValuation": VALUATION_ID,
}


def flight_push(row: str) -> str:
    return f"<script>self.__next_f.push([1,{json.dumps(row)}])</script>"


def page_html(build: str | None = "BUILD_a1-b2", chunks: tuple[str, ...] = ()) -> str:
    scripts = "".join(
        f'<script src="{path}" async=""></script>' for path in (RUNTIME, MAIN, PAGE_CHUNK, *chunks)
    )
    rows = flight_push('2:["$","$L1",null,{"data":{"b":"not-the-build"}}]\n')
    if build is not None:
        rows = flight_push(f'0:{{"P":null,"b":"{build}","p":"","i":false}}\n') + rows
    return f"<!DOCTYPE html><html><head>{scripts}</head><body>{rows}</body></html>"


def html_response(html: str, status: int = 200, **headers: str) -> Response:
    names = {key.replace("_", "-").lower(): value for key, value in headers.items()}
    return Response(status, {"content-type": "text/html; charset=utf-8", **names}, html.encode())


def js_response(text: str) -> Response:
    return Response(200, {"content-type": "application/javascript"}, text.encode())


def response(status: int, body: bytes = b"", **headers: str) -> Response:
    names = {key.replace("_", "-").lower(): value for key, value in headers.items()}
    return Response(status, names, body)


CHALLENGE_HTML = (
    "<!DOCTYPE html><html><head><title>Just a moment...</title></head>"
    "<body><script>window._cf_chl_opt={cType:'managed'};</script></body></html>"
)


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


@dataclass
class FakeSite:
    """Mocked transport: every page of PAGES and every fixture chunk; records requests.

    ``overrides`` replaces the answer for a path; unknown paths get a 404.
    """

    lock_path: Path
    overrides: dict[str, Response] = field(default_factory=dict)
    page: str = field(default_factory=page_html)
    requests: list[tuple[str, dict[str, str], float]] = field(default_factory=list)
    lock_held: list[bool] = field(default_factory=list)

    def __call__(self, url: str, headers: Mapping[str, str], timeout: float) -> Response:
        self.requests.append((url, dict(headers), timeout))
        self.lock_held.append(lock_is_held(self.lock_path))
        assert url.startswith(identity.BASE_URL + "/")
        path = url.removeprefix(identity.BASE_URL)
        if path in self.overrides:
            return self.overrides[path]
        if path in scan_bundles.PAGES:
            return html_response(self.page)
        if path in CHUNK_JS:
            return js_response(CHUNK_JS[path])
        return response(404, b"not found")

    @property
    def paths(self) -> list[str]:
        return [url.removeprefix(identity.BASE_URL) for url, _, _ in self.requests]


@dataclass
class Env:
    limiter: RequestLimiter
    lock_dir: Path
    cache_dir: Path

    def site(self, **kw: Any) -> FakeSite:
        return FakeSite(self.lock_dir / LOCK_FILENAME, **kw)

    def run(self, argv: list[str], site: Callable[..., Response]) -> int:
        return scan_bundles.main(argv, fetch=site, limiter=self.limiter, cache_dir=self.cache_dir)

    def pause_after_last_request(self) -> float:
        state = json.loads((self.lock_dir / LOCK_FILENAME).read_text())
        return float(state["next_start"] - state["last_end"])


@pytest.fixture
def env(tmp_path: Path) -> Env:
    lock_dir = tmp_path / "lock"
    # min_interval=0 keeps the suite fast; any pause in the lock file comes from defer().
    limiter = RequestLimiter(lock_dir, min_interval=0, testing_only_allow_fast_interval=True)
    return Env(limiter, lock_dir, tmp_path / "cache" / "chunks")


def scan_json(
    env: Env, site: FakeSite, capsys: pytest.CaptureFixture[str]
) -> tuple[dict[str, Any], str]:
    """A successful ``--json`` run: the parsed stdout and the stderr."""
    assert env.run(["--json"], site) == 0
    captured = capsys.readouterr()
    data: dict[str, Any] = json.loads(captured.out)
    return data, captured.err


ALL_CHUNKS = sorted(CHUNK_JS)


# --- requests: limiter, identity, order ---------------------------------------------


def test_every_request_runs_in_the_limiter_with_the_shared_identity(env: Env) -> None:
    site = env.site()

    assert env.run(["--json"], site) == 0

    assert len(site.requests) == len(scan_bundles.PAGES) + len(CHUNK_JS)
    assert site.lock_held == [True] * len(site.requests)
    assert not lock_is_held(env.lock_dir / LOCK_FILENAME)
    for url, headers, timeout in site.requests:
        assert url.startswith(identity.BASE_URL + "/")
        assert headers == {"User-Agent": identity.USER_AGENT}
        assert timeout == http_common.TIMEOUT


def test_pages_first_then_runtime_then_the_other_chunks(env: Env) -> None:
    site = env.site()

    env.run([], site)

    pages = len(scan_bundles.PAGES)
    assert site.paths[:pages] == scan_bundles.PAGES
    assert site.paths[pages] == RUNTIME
    assert site.paths[pages + 1 :] == sorted(set(CHUNK_JS) - {RUNTIME})


def test_wait_too_long_sends_nothing(env: Env, capsys: pytest.CaptureFixture[str]) -> None:
    with env.limiter.slot() as slot:
        slot.defer(600)
    site = env.site()

    assert env.run(["--json"], site) == WAIT
    assert site.requests == []
    captured = capsys.readouterr()
    assert "600 s" in captured.err
    assert captured.out == ""


# --- output ---------------------------------------------------------------------------


def test_json_output_format(env: Env, capsys: pytest.CaptureFixture[str]) -> None:
    data, _ = scan_json(env, env.site(), capsys)

    assert data == {
        "build_id": "BUILD_a1-b2",
        "pages": len(scan_bundles.PAGES),
        "chunks": len(CHUNK_JS),
        "chunks_fetched": len(CHUNK_JS),
        "chunks_cached": 0,
        "api": EXPECTED_API,
        "actions": EXPECTED_ACTIONS,
        "incomplete": [],
    }
    assert list(data["actions"]) == sorted(EXPECTED_ACTIONS)


def test_text_output(env: Env, capsys: pytest.CaptureFixture[str]) -> None:
    assert env.run([], env.site()) == 0

    out = capsys.readouterr().out
    assert "BUILD_a1-b2" in out
    for path in EXPECTED_API:
        assert f"  {path}\n" in out
    for name, action_id in EXPECTED_ACTIONS.items():
        assert re.search(rf"^  {name} +{action_id}$", out, re.M)
    assert "NIEPEŁNY" not in out


def test_text_output_lists_why_the_result_is_incomplete(
    env: Env, capsys: pytest.CaptureFixture[str]
) -> None:
    site = env.site(overrides={RUNTIME: js_response("(()=>{})();")})

    assert env.run([], site) == 0

    out = capsys.readouterr().out
    assert "NIEPEŁNY WYNIK" in out
    assert "Leniwe chunki pominięte" in out


def test_progress_goes_to_stderr(env: Env, capsys: pytest.CaptureFixture[str]) -> None:
    env.run(["--json"], env.site())

    err = capsys.readouterr().err
    assert f"GET {RUNTIME}: HTTP 200" in err
    assert "GET /: HTTP 200, text/html" in err


# --- cache ------------------------------------------------------------------------------


def cached_file(env: Env, path: str) -> Path:
    return env.cache_dir.joinpath(*path.removeprefix(CHUNKS).split("/"))


def test_chunks_are_cached_under_their_path(env: Env) -> None:
    env.run(["--json"], env.site())

    for path, text in CHUNK_JS.items():
        assert cached_file(env, path).read_bytes() == text.encode()
    nested = env.cache_dir / "app" / "ceny-ofertowe" / "%5Bcity%5D" / "mieszkania"
    assert (nested / "page-fedcba9876543210.js").is_file()


def test_second_run_takes_chunks_from_the_cache(
    env: Env, capsys: pytest.CaptureFixture[str]
) -> None:
    first, _ = scan_json(env, env.site(), capsys)
    site = env.site()

    second, _ = scan_json(env, site, capsys)

    assert site.paths == scan_bundles.PAGES  # pages only: they name the current chunks
    assert (second["chunks_fetched"], second["chunks_cached"]) == (0, len(CHUNK_JS))
    assert {k: v for k, v in second.items() if not k.startswith("chunks_")} == {
        k: v for k, v in first.items() if not k.startswith("chunks_")
    }


def test_new_chunk_of_a_deploy_is_fetched_once(
    env: Env, capsys: pytest.CaptureFixture[str]
) -> None:
    scan_json(env, env.site(), capsys)
    new = CHUNKS + "app/wycena/page-1234567890abcdef.js"
    page = page_html(chunks=(new,))
    site = env.site(page=page, overrides={new: js_response('fetch("/api/new-endpoint")')})

    data, _ = scan_json(env, site, capsys)

    assert site.paths[len(scan_bundles.PAGES) :] == [new]
    assert "/api/new-endpoint" in data["api"]
    assert (data["chunks_fetched"], data["chunks_cached"]) == (1, len(CHUNK_JS))


def test_chunk_without_a_content_hash_is_never_taken_from_the_cache(
    env: Env, capsys: pytest.CaptureFixture[str]
) -> None:
    plain = CHUNKS + "app/layout.js"
    site = env.site(page=page_html(chunks=(plain,)), overrides={plain: js_response("var a;")})
    scan_json(env, site, capsys)
    again = env.site(page=page_html(chunks=(plain,)), overrides={plain: js_response("var b;")})

    data, _ = scan_json(env, again, capsys)

    assert again.paths[len(scan_bundles.PAGES) :] == [plain]
    assert cached_file(env, plain).read_text() == "var b;"  # kept for offline analysis
    assert (data["chunks_fetched"], data["chunks_cached"]) == (1, len(CHUNK_JS))


def test_cache_write_is_atomic(env: Env, monkeypatch: pytest.MonkeyPatch) -> None:
    real_replace = os.replace
    replaced: list[tuple[Path, Path]] = []

    def checked_replace(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        source, target = Path(src), Path(dst)
        assert not target.exists()  # the final name appears only complete
        assert source.parent == target.parent  # same file system: rename is atomic
        assert source.name.startswith(".")
        assert (
            source.read_bytes()
            == CHUNK_JS[CHUNKS + "/".join(target.relative_to(env.cache_dir).parts)].encode()
        )
        replaced.append((source, target))
        real_replace(src, dst)

    monkeypatch.setattr(os, "replace", checked_replace)

    env.run(["--json"], env.site())

    assert sorted(target for _, target in replaced) == sorted(
        cached_file(env, path) for path in CHUNK_JS
    )
    assert not any(source.exists() for source, _ in replaced)


def test_failed_cache_write_leaves_nothing_and_the_scan_goes_on(
    env: Env, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def disk_full(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(os, "replace", disk_full)

    data, err = scan_json(env, env.site(), capsys)

    assert data["api"] == EXPECTED_API
    assert data["incomplete"] == []  # the cache is an optimisation, not part of the result
    assert [p for p in env.cache_dir.rglob("*") if p.is_file()] == []
    assert "Info: nie zapisano" in err
    assert "No space left" in err


def test_unreadable_cache_entry_is_fetched_again(
    env: Env, capsys: pytest.CaptureFixture[str]
) -> None:
    cached_file(env, MAIN).mkdir(parents=True)  # a directory where the file should be
    site = env.site()

    data, err = scan_json(env, site, capsys)

    assert MAIN in site.paths
    assert data["api"] == EXPECTED_API
    assert data["incomplete"] == []
    assert "Info: nie można odczytać" in err
    assert "Info: nie zapisano" in err  # os.replace cannot put a file over a directory
    assert cached_file(env, MAIN).is_dir()
    assert list(env.cache_dir.rglob("*.tmp")) == []  # no temporary file left behind


def test_empty_cache_entry_is_fetched_again(env: Env, capsys: pytest.CaptureFixture[str]) -> None:
    cached_file(env, MAIN).parent.mkdir(parents=True)
    cached_file(env, MAIN).write_bytes(b"")
    site = env.site()

    data, _ = scan_json(env, site, capsys)

    assert MAIN in site.paths
    assert cached_file(env, MAIN).read_bytes() == CHUNK_JS[MAIN].encode()
    assert data["api"] == EXPECTED_API


@pytest.mark.parametrize(
    "reply",
    [
        response(200, b"", content_type="application/javascript"),
        response(204),
        response(203, b'fetch("/api/partial")', content_type="application/javascript"),
    ],
    ids=["200 empty", "204", "203"],
)
def test_chunk_without_a_full_200_body_is_not_used_or_cached(
    env: Env, capsys: pytest.CaptureFixture[str], reply: Response
) -> None:
    data, err = scan_json(env, env.site(overrides={MAIN: reply}), capsys)

    assert not cached_file(env, MAIN).exists()
    assert len(data["incomplete"]) == 1
    assert MAIN in data["incomplete"][0]
    assert f"Uwaga (niepełny wynik): GET {MAIN}" in err
    assert "/api/partial" not in data["api"]
    assert (data["chunks_fetched"], data["chunks_cached"]) == (len(CHUNK_JS) - 1, 0)

    site = env.site()
    again, _ = scan_json(env, site, capsys)

    assert site.paths[len(scan_bundles.PAGES) :] == [MAIN]  # not trusted from the cache
    assert again["incomplete"] == []


def test_default_cache_dir_follows_xdg(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    assert scan_bundles.default_cache_dir() == tmp_path / "deweloperuch-mcp" / "chunks"

    monkeypatch.setenv("XDG_CACHE_HOME", "relative/dir")  # ignored, as XDG requires
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    expected = tmp_path / "home" / ".cache" / "deweloperuch-mcp" / "chunks"
    assert scan_bundles.default_cache_dir() == expected


# --- STOP and other failures --------------------------------------------------------


@pytest.mark.parametrize(
    ("index", "reply", "pause"),
    [
        (2, response(429, b"slow down", retry_after="120"), 120.0),
        (0, response(429), 60.0),
        (5, response(403, b"forbidden"), 0.0),
        (1, response(401), 0.0),
        (3, html_response(CHALLENGE_HTML), 0.0),
        (4, response(503, CHALLENGE_HTML.encode(), cf_mitigated="challenge"), 30.0),
    ],
)
def test_stop_on_a_page_ends_the_scan(
    env: Env,
    capsys: pytest.CaptureFixture[str],
    index: int,
    reply: Response,
    pause: float,
) -> None:
    page = scan_bundles.PAGES[index]
    site = env.site(overrides={page: reply})

    assert env.run(["--json"], site) == STOP

    assert site.paths == scan_bundles.PAGES[: index + 1]  # nothing after the STOP
    assert env.pause_after_last_request() == pytest.approx(pause, abs=0.01)
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "STOP" in captured.err
    assert page in captured.err
    assert "Przerwij serię" in captured.err


@pytest.mark.parametrize(
    ("chunk", "reply", "pause"),
    [
        (RUNTIME, response(429, retry_after="90"), 90.0),
        (MAIN, response(403), 0.0),
        (LAZY_BY_ID, response(429), 60.0),
        (PAGE_CHUNK, html_response(CHALLENGE_HTML), 0.0),
    ],
)
def test_stop_on_a_chunk_ends_the_scan(
    env: Env,
    capsys: pytest.CaptureFixture[str],
    chunk: str,
    reply: Response,
    pause: float,
) -> None:
    site = env.site(overrides={chunk: reply})

    assert env.run(["--json"], site) == STOP

    assert site.paths[-1] == chunk
    assert site.paths.count(chunk) == 1
    assert env.pause_after_last_request() == pytest.approx(pause, abs=0.01)
    assert not cached_file(env, chunk).exists()
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "STOP" in captured.err


@pytest.mark.parametrize(
    ("reply", "pause", "hint"),
    [
        (response(503, b"maintenance", retry_after="45"), 45.0, "maintenance"),
        (response(502), 30.0, "HTTP 502"),
        (response(500, b"oops"), 0.0, "oops"),
        (response(404, b"gone"), 0.0, "gone"),
        (response(308, location="/elsewhere"), 0.0, "PAGES"),
        (Response(200, {}, b"x" * 10, "Odpowiedź przekracza 10 B (D5)."), 0.0, "D5"),
    ],
)
def test_other_failures_end_the_scan_without_retry(
    env: Env,
    capsys: pytest.CaptureFixture[str],
    reply: Response,
    pause: float,
    hint: str,
) -> None:
    page = scan_bundles.PAGES[1]
    site = env.site(overrides={page: reply})

    assert env.run(["--json"], site) == HTTP_ERROR

    assert site.paths == scan_bundles.PAGES[:2]
    assert env.pause_after_last_request() == pytest.approx(pause, abs=0.01)
    captured = capsys.readouterr()
    assert captured.out == ""
    assert hint in captured.err


def test_network_error_ends_the_scan(env: Env, capsys: pytest.CaptureFixture[str]) -> None:
    calls: list[str] = []

    def failing(url: str, headers: Mapping[str, str], timeout: float) -> Response:
        calls.append(url)
        raise TimeoutError("timed out")

    assert env.run(["--json"], failing) == HTTP_ERROR
    assert len(calls) == 1
    assert "Błąd sieci" in capsys.readouterr().err


def test_chunk_served_as_html_is_not_cached(env: Env, capsys: pytest.CaptureFixture[str]) -> None:
    site = env.site(overrides={MAIN: html_response("<!DOCTYPE html><html>404</html>")})

    assert env.run(["--json"], site) == NO_DATA

    assert site.paths[-1] == MAIN
    assert not cached_file(env, MAIN).exists()
    assert "HTML" in capsys.readouterr().err


def test_pages_without_chunks_are_an_error(env: Env, capsys: pytest.CaptureFixture[str]) -> None:
    site = env.site(page="<!DOCTYPE html><html><body>maintenance</body></html>")

    assert env.run(["--json"], site) == NO_DATA

    assert site.paths == scan_bundles.PAGES
    assert capsys.readouterr().out == ""


# --- allowlist --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    [
        *scan_bundles.PAGES,
        RUNTIME,
        PAGE_CHUNK,
        CHUNKS + "app/(main)/[city]/page-0123456789abcdef.js",
        CHUNKS + "1234.0123456789abcdef.js",
        CHUNKS + "app/%28main%29/%5bcity%5d/page-0123456789abcdef.js",  # escapes, any case
    ],
)
def test_allowlist_accepts_pages_and_chunks(path: str) -> None:
    assert scan_bundles.is_scan_path(path)


@pytest.mark.parametrize(
    "path",
    [
        "/api/cities",
        "/api/cities?q=krak",
        "/ceny-ofertowe/krakow/mieszkania",  # a valid route, but not on PAGES
        "/wycena?x=1",
        "/wycena/",
        "",
        "https://" + "deweloperuch" + ".pl/",
        "//example.com" + CHUNKS + "a.js",
        CHUNKS + "a.css",
        CHUNKS + "a.js?v=1",
        CHUNKS + "a.js#x",
        CHUNKS + ".js",
        "/_next/static/css/a.js",
        "/_next/static/chunks.js",
        "/_next/data/build/page.json",
        CHUNKS + "../../../api/cities.js",
        CHUNKS + "app/../x.js",
        CHUNKS + "./x.js",
        CHUNKS + "app//x.js",
        CHUNKS + "%2e%2e/x.js",
        CHUNKS + "a%2Fb.js",
        CHUNKS + "a%5cb.js",
        CHUNKS + "a%zz.js",
        # Only %5B %5D %28 %29 may appear: anything else could decode into a traversal,
        # also on a server that decodes twice.
        CHUNKS + "%252F..%252Fx.dddddddd.js",
        CHUNKS + "%25.js",
        CHUNKS + "a%41.js",
        CHUNKS + "%2e.js",
        CHUNKS + "a%5.js",
        CHUNKS + "a\\b.js",
        CHUNKS + "a b.js",
        CHUNKS + "a\n.js",
    ],
)
def test_allowlist_rejects_everything_else(path: str) -> None:
    assert not scan_bundles.is_scan_path(path)


def test_disallowed_chunk_in_a_page_is_skipped_with_a_warning(
    env: Env, capsys: pytest.CaptureFixture[str]
) -> None:
    sneaky = CHUNKS + "../../../api/cities.js"
    site = env.site(page=page_html(chunks=(sneaky,)))

    data, err = scan_json(env, site, capsys)

    assert not any("api/cities" in path for path in site.paths)
    assert data["chunks"] == len(CHUNK_JS)
    assert f"Uwaga (niepełny wynik): pomijam {sneaky!r}" in err
    assert [sneaky in reason for reason in data["incomplete"]] == [True]


HOSTILE_NAMES = {1: "../../api/x", 2: "a?b", 3: "//evil.com/x", 4: "%252F..%252Fx"}
LAZY_OK = CHUNKS + "5.0123456789abcdef.js"


def hostile_runtime() -> str:
    names = ",".join(f'{key}:"{name}"' for key, name in HOSTILE_NAMES.items())
    hashes = ",".join(f'{key}:"dddddddd"' for key in HOSTILE_NAMES) + ',5:"0123456789abcdef"'
    return f'r.u=e=>"static/chunks/"+(({{{names}}})[e]||e)+"."+({{{hashes}}})[e]+".js"'


def test_hostile_names_in_the_runtime_map_are_never_requested(
    env: Env, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "scan.json"
    site = env.site(
        overrides={
            RUNTIME: js_response(hostile_runtime()),
            LAZY_OK: js_response('fetch("/api/lazy-ok")'),
        }
    )

    code = env.run(["--json", "--baseline-out", str(target)], site)

    assert code == NO_DATA  # incomplete: no baseline
    assert not target.exists()
    assert site.paths == [*scan_bundles.PAGES, RUNTIME, *sorted({MAIN, PAGE_CHUNK, LAZY_OK})]
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "/api/lazy-ok" in data["api"]
    assert len(data["incomplete"]) == len(HOSTILE_NAMES)
    for name in HOSTILE_NAMES.values():
        assert f"Uwaga (niepełny wynik): pomijam '{CHUNKS}{name}.dddddddd.js'" in captured.err


def test_request_outside_the_allowlist_is_refused_before_sending(env: Env) -> None:
    site = env.site()
    scanner = scan_bundles.Scanner(site, env.limiter, env.cache_dir)

    with pytest.raises(scan_bundles.ScanError) as exc:
        scanner.page("/api/cities")
    with pytest.raises(scan_bundles.ScanError):
        scanner.chunk(CHUNKS + "../x.js")
    with pytest.raises(scan_bundles.ScanError):
        scanner.chunk(scan_bundles.PAGES[0])  # a page is not a chunk

    assert exc.value.code == USAGE
    assert site.requests == []


# --- extraction ---------------------------------------------------------------------------


def test_build_id_from_the_rsc_payload_of_the_page() -> None:
    assert scan_bundles.build_id(page_html("KD_IOP6Grqba7xa86pGVG")) == "KD_IOP6Grqba7xa86pGVG"


def test_build_id_is_not_any_b_key() -> None:
    # Row 2 has {"b": ...} in its data; without row 0 there is no build ID.
    assert scan_bundles.build_id(page_html(None)) is None
    # A data row that is itself an object with "b" (rows 10 and a0 start like row 0).
    rows = '3:{"b":"data-3","c":1}\n10:{"b":"data-10"}\na0:{"b":"data-a0"}\n'
    assert scan_bundles.build_id(flight_push(rows)) is None
    assert scan_bundles.build_id(flight_push(rows + '0:{"b":"REAL_1"}\n')) == "REAL_1"


def test_build_id_from_next_data() -> None:
    html = '<script id="__NEXT_DATA__" type="application/json">{"buildId":"abc_DEF-1"}</script>'

    assert scan_bundles.build_id(html) == "abc_DEF-1"


@pytest.mark.parametrize("value", ['"x\\u001b[31m"', '"a b"', '""', "123", '"' + "x" * 200 + '"'])
def test_odd_build_id_values_are_ignored(value: str) -> None:
    html = flight_push(f'0:{{"P":null,"b":{value}}}\n')

    assert scan_bundles.build_id(html) is None


def test_missing_build_id_is_reported(env: Env, capsys: pytest.CaptureFixture[str]) -> None:
    data, err = scan_json(env, env.site(page=page_html(None)), capsys)

    assert data["build_id"] is None
    assert data["incomplete"] == []  # paths and actions do not depend on the build ID
    assert "Info: nie znaleziono build ID" in err
    assert "niepełny" not in err


def test_build_id_change_during_the_scan_is_reported(
    env: Env, capsys: pytest.CaptureFixture[str]
) -> None:
    deployed = scan_bundles.PAGES[-1]
    site = env.site(overrides={deployed: html_response(page_html("NEW_build"))})

    data, err = scan_json(env, site, capsys)

    assert data["build_id"] == "BUILD_a1-b2"
    assert "Uwaga (niepełny wynik): strony podały różne build ID" in err
    assert "BUILD_a1-b2" in err
    assert "NEW_build" in err
    assert len(data["incomplete"]) == 1


def test_chunk_paths_in_html() -> None:
    html = page_html(chunks=(MAIN,)) + '<link href="/_next/static/css/a.css" rel="stylesheet">'

    assert scan_bundles.chunk_paths(html) == {RUNTIME, MAIN, PAGE_CHUNK}


def test_lazy_chunks_from_the_webpack_runtime() -> None:
    assert scan_bundles.lazy_chunks(RUNTIME_JS) == {LAZY_NAMED, LAZY_BY_ID, LAZY_FIXED}


@pytest.mark.parametrize(
    "runtime",
    [
        "(()=>{})();",  # no chunk map: bundler or format changed
        RUNTIME_JS.replace('"eeee5555ffff6666"', "x"),  # map that is not a literal
        RUNTIME_JS.replace('{123:"vendors"}', '{123:["vendors"]}'),
        # Nested deeper than the JSON decoder's recursion limit (RecursionError).
        RUNTIME_JS.replace('{123:"vendors"}', "{123:" + "[" * 100_000 + "]" * 100_000 + "}"),
    ],
    ids=["no map", "not a literal", "not a string", "too deep"],
)
def test_unreadable_runtime_map_raises(runtime: str) -> None:
    with pytest.raises(ValueError):
        scan_bundles.lazy_chunks(runtime)


def test_missing_lazy_map_is_reported(env: Env, capsys: pytest.CaptureFixture[str]) -> None:
    site = env.site(overrides={RUNTIME: js_response("(()=>{})();")})

    data, err = scan_json(env, site, capsys)  # exit 0: neither --compare nor --baseline-out

    assert data["chunks"] == 3  # runtime, main, page chunk
    assert "Uwaga (niepełny wynik): Runtime webpacka" in err
    assert len(data["incomplete"]) == 1


def test_too_deep_runtime_map_is_an_incomplete_result(
    env: Env, capsys: pytest.CaptureFixture[str]
) -> None:
    deep = RUNTIME_JS.replace('{123:"vendors"}', "{123:" + "[" * 100_000 + "]" * 100_000 + "}")
    site = env.site(overrides={RUNTIME: js_response(deep)})

    data, err = scan_json(env, site, capsys)

    assert data["chunks"] == 3
    assert "Uwaga (niepełny wynik): Nieczytelna mapa chunków" in err


def test_missing_runtime_is_reported(env: Env, capsys: pytest.CaptureFixture[str]) -> None:
    html = page_html().replace(RUNTIME, CHUNKS + "turbopack-0123456789abcdef.js")
    site = env.site(
        page=html,
        overrides={CHUNKS + "turbopack-0123456789abcdef.js": js_response("var t;")},
    )

    data, err = scan_json(env, site, capsys)

    assert "Uwaga (niepełny wynik): nie znaleziono runtime'u webpacka" in err
    assert len(data["incomplete"]) == 1


# --- limit of chunk requests ---------------------------------------------------------------


def test_too_many_chunks_in_the_pages_stop_before_any_chunk_request(
    env: Env, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(scan_bundles, "MAX_CHUNKS", 2)  # the pages name 3 chunks
    site = env.site()

    assert env.run(["--json"], site) == NO_DATA

    assert site.paths == scan_bundles.PAGES
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "limit 2" in captured.err


def test_huge_lazy_map_stops_before_fetching_it(
    env: Env, capsys: pytest.CaptureFixture[str]
) -> None:
    """The map is known only after the runtime: nothing else is fetched once it is read."""
    entries = scan_bundles.MAX_CHUNKS + 100
    hashes = ",".join(f'{i}:"{i:016x}"' for i in range(entries))
    runtime = f'r.u=e=>"static/chunks/"+(({{}})[e]||e)+"."+({{{hashes}}})[e]+".js"'
    site = env.site(overrides={RUNTIME: js_response(runtime)})

    assert env.run(["--json"], site) == NO_DATA

    assert site.paths == [*scan_bundles.PAGES, RUNTIME]
    assert f"limit {scan_bundles.MAX_CHUNKS}" in capsys.readouterr().err


def test_cached_chunks_do_not_count_against_the_limit(
    env: Env, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    scan_json(env, env.site(), capsys)
    monkeypatch.setattr(scan_bundles, "MAX_CHUNKS", 1)
    new = CHUNKS + "app/wycena/page-1234567890abcdef.js"
    site = env.site(page=page_html(chunks=(new,)), overrides={new: js_response("var n;")})

    data, _ = scan_json(env, site, capsys)

    assert site.paths[len(scan_bundles.PAGES) :] == [new]
    assert (data["chunks_fetched"], data["chunks_cached"]) == (1, len(CHUNK_JS))


def test_chunk_limit_is_the_agreed_one() -> None:
    assert scan_bundles.MAX_CHUNKS == 400


def chunk_requests(site: FakeSite) -> list[str]:
    return [path for path in site.paths if path not in scan_bundles.PAGES]


@pytest.mark.skipif(os.geteuid() == 0, reason="root reads files with mode 000")
def test_unreadable_cache_files_cannot_exceed_the_limit(
    env: Env, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The estimate counts them as cached (they stat fine); the hard limit still holds."""
    scan_json(env, env.site(), capsys)
    files = [cached_file(env, path) for path in CHUNK_JS]
    monkeypatch.setattr(scan_bundles, "MAX_CHUNKS", 1)
    site = env.site()
    try:
        for file in files:
            file.chmod(0)
        code = env.run(["--json"], site)
    finally:
        for file in files:
            file.chmod(0o600)

    assert code == NO_DATA
    assert chunk_requests(site) == [RUNTIME]  # the first one fits the limit of 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "limit 1" in captured.err


def test_empty_cache_files_count_as_missing_for_the_limit(
    env: Env, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """An empty file is no cached chunk: the estimate stops before any chunk request."""
    scan_json(env, env.site(), capsys)
    for path in CHUNK_JS:
        cached_file(env, path).write_bytes(b"")
    monkeypatch.setattr(scan_bundles, "MAX_CHUNKS", 1)
    site = env.site()

    assert env.run(["--json"], site) == NO_DATA

    assert chunk_requests(site) == []
    assert "limit 1" in capsys.readouterr().err


def test_hard_limit_counts_every_chunk_request(env: Env) -> None:
    """Also requests whose body is rejected; nothing is sent once the limit is reached."""
    site = env.site(overrides={MAIN: response(204)})  # sent, but not a usable chunk
    scanner = scan_bundles.Scanner(site, env.limiter, env.cache_dir)
    scanner.chunk(MAIN)
    scanner.chunk(RUNTIME)

    assert (scanner.requested, scanner.fetched) == (2, 1)
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(scan_bundles, "MAX_CHUNKS", 2)
        with pytest.raises(scan_bundles.ScanError) as exc:
            scanner.chunk(PAGE_CHUNK)

    assert exc.value.code == NO_DATA
    assert chunk_requests(site) == [MAIN, RUNTIME]


def test_api_paths_and_actions() -> None:
    js = "".join(CHUNK_JS.values())

    assert sorted(scan_bundles.api_paths(js)) == EXPECTED_API
    assert scan_bundles.server_actions(js) == EXPECTED_ACTIONS


# --- baseline and --compare -------------------------------------------------------------


def write_baseline(tmp_path: Path, data: Any) -> Path:
    path = tmp_path / "scan.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_compare_without_differences(
    env: Env, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    baseline = write_baseline(tmp_path, {"api": EXPECTED_API, "actions": sorted(EXPECTED_ACTIONS)})

    assert env.run(["--compare", str(baseline)], env.site()) == 0
    assert "brak różnic" in capsys.readouterr().out


def test_compare_reports_new_and_removed(
    env: Env, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    baseline = write_baseline(
        tmp_path,
        {
            "api": [
                "/api/cities?q=",
                "/api/gone",
                "/api/map/investments",
                "/api/offer-count?city=",
            ],
            "actions": ["fetchStandaloneValuation", "removedAction"],
        },
    )

    assert env.run(["--json", "--compare", str(baseline)], env.site()) == DRIFT

    data = json.loads(capsys.readouterr().out)
    assert data["drift"] == {
        "api_added": ["/api/investments/${t}/sale-events"],
        "api_removed": ["/api/gone"],
        "actions_added": ["createInvestmentAction"],
        "actions_removed": ["removedAction"],
    }
    assert data["api"] == EXPECTED_API  # the scan result is still complete


def test_compare_text_lists_the_differences(
    env: Env, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    baseline = write_baseline(tmp_path, {"api": ["/api/gone"], "actions": []})

    assert env.run(["--compare", str(baseline)], env.site()) == DRIFT

    out = capsys.readouterr().out
    assert "+ /api/cities?q=" in out
    assert "- /api/gone" in out
    assert "+ fetchStandaloneValuation" in out


def test_compare_ignores_action_ids_and_build_id(
    env: Env, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    previous = {
        "build_id": "OLD_build",
        "api": EXPECTED_API,
        "actions": {name: "f" * 42 for name in EXPECTED_ACTIONS},  # IDs of another deploy
    }
    baseline = write_baseline(tmp_path, previous)

    assert env.run(["--json", "--compare", str(baseline)], env.site()) == 0
    assert json.loads(capsys.readouterr().out)["drift"] == {
        "api_added": [],
        "api_removed": [],
        "actions_added": [],
        "actions_removed": [],
    }


@pytest.mark.parametrize(
    "content",
    [
        "not json",
        "[]",
        '{"api": []}',
        '{"actions": []}',
        '{"api": "/api/cities", "actions": []}',
        '{"api": [1], "actions": []}',
        '{"api": [], "actions": [null]}',
        '{"api": [], "actions": {"a": 1, "b": 2}, "x": 1}',
    ],
)
def test_bad_baseline_is_refused_before_any_request(
    env: Env, tmp_path: Path, capsys: pytest.CaptureFixture[str], content: str
) -> None:
    path = tmp_path / "scan.json"
    path.write_text(content, encoding="utf-8")
    site = env.site()

    assert env.run(["--compare", str(path)], site) == USAGE
    assert site.requests == []
    assert "baseline" in capsys.readouterr().err


def test_missing_baseline_is_refused_before_any_request(
    env: Env, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    site = env.site()

    assert env.run(["--compare", str(tmp_path / "missing.json")], site) == USAGE
    assert site.requests == []
    assert "--baseline-out" in capsys.readouterr().err


def test_baseline_out_writes_names_only_sorted(
    env: Env, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "baseline" / "scan.json"
    target.parent.mkdir()

    assert env.run(["--json", "--baseline-out", str(target)], env.site()) == 0

    assert json.loads(target.read_text(encoding="utf-8")) == {
        "api": EXPECTED_API,
        "actions": sorted(EXPECTED_ACTIONS),
    }
    assert target.read_text(encoding="utf-8").endswith("\n")
    assert [p.name for p in target.parent.iterdir()] == ["scan.json"]  # no temp files left
    capsys.readouterr()
    assert env.run(["--compare", str(target)], env.site()) == 0


def test_baseline_out_replaces_the_old_baseline_after_comparing(
    env: Env, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    baseline = write_baseline(tmp_path, {"api": ["/api/gone"], "actions": []})

    code = env.run(["--compare", str(baseline), "--baseline-out", str(baseline)], env.site())

    assert code == DRIFT
    assert json.loads(baseline.read_text(encoding="utf-8"))["api"] == EXPECTED_API


def test_baseline_out_in_a_missing_directory_is_refused_before_any_request(
    env: Env, tmp_path: Path
) -> None:
    site = env.site()

    code = env.run(["--baseline-out", str(tmp_path / "missing" / "scan.json")], site)

    assert code == USAGE
    assert site.requests == []


@pytest.mark.parametrize("option", ["--baseline-out", "--compare"])
def test_directory_instead_of_a_file_is_refused_before_any_request(
    env: Env, tmp_path: Path, capsys: pytest.CaptureFixture[str], option: str
) -> None:
    site = env.site()

    assert env.run([option, str(tmp_path)], site) == USAGE
    assert site.requests == []
    assert str(tmp_path) in capsys.readouterr().err


def test_failed_baseline_write_is_a_usage_error_and_keeps_the_old_file(
    env: Env, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "baseline" / "scan.json"
    target.parent.mkdir()
    target.write_text("previous", encoding="utf-8")
    real_replace = os.replace

    def failing_for_target(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        if Path(dst) == target:
            raise OSError(28, "No space left on device")
        real_replace(src, dst)

    monkeypatch.setattr(os, "replace", failing_for_target)

    assert env.run(["--json", "--baseline-out", str(target)], env.site()) == USAGE

    assert target.read_text(encoding="utf-8") == "previous"
    assert [p.name for p in target.parent.iterdir()] == ["scan.json"]  # temp file removed
    captured = capsys.readouterr()
    assert json.loads(captured.out)["api"] == EXPECTED_API
    assert "Nie udało się zapisać baseline" in captured.err


def test_failed_scan_writes_no_baseline(env: Env, tmp_path: Path) -> None:
    target = tmp_path / "scan.json"
    site = env.site(overrides={MAIN: response(429)})

    assert env.run(["--baseline-out", str(target)], site) == STOP
    assert not target.exists()


INCOMPLETE_SCANS = {
    "no lazy chunk map": {"overrides": {RUNTIME: js_response("(()=>{})();")}},
    "chunk off the allowlist": {"page": page_html(chunks=(CHUNKS + "../x.js",))},
    "build changed mid-scan": {
        "overrides": {scan_bundles.PAGES[-1]: html_response(page_html("NEW_build"))}
    },
    "empty chunk": {"overrides": {MAIN: response(200, content_type="application/javascript")}},
}


@pytest.mark.parametrize("site_kw", INCOMPLETE_SCANS.values(), ids=list(INCOMPLETE_SCANS))
def test_incomplete_scan_writes_no_baseline(
    env: Env, tmp_path: Path, capsys: pytest.CaptureFixture[str], site_kw: dict[str, Any]
) -> None:
    target = tmp_path / "scan.json"
    target.write_text("previous", encoding="utf-8")

    code = env.run(["--json", "--baseline-out", str(target)], env.site(**site_kw))

    assert code == NO_DATA
    assert target.read_text(encoding="utf-8") == "previous"
    captured = capsys.readouterr()
    assert json.loads(captured.out)["api"]  # the result itself is still printed
    assert "nie został zapisany" in captured.err


@pytest.mark.parametrize("site_kw", INCOMPLETE_SCANS.values(), ids=list(INCOMPLETE_SCANS))
@pytest.mark.parametrize("same_as_baseline", [True, False], ids=["no diff", "diff"])
def test_incomplete_scan_with_compare_is_code_6_not_0_or_7(
    env: Env,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    site_kw: dict[str, Any],
    same_as_baseline: bool,
) -> None:
    api = EXPECTED_API if same_as_baseline else ["/api/gone"]
    baseline = write_baseline(tmp_path, {"api": api, "actions": sorted(EXPECTED_ACTIONS)})

    code = env.run(["--json", "--compare", str(baseline)], env.site(**site_kw))

    assert code == NO_DATA
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["incomplete"]
    assert "drift" in data  # printed, but only indicative
    assert "orientacyjne" in captured.err


def test_missing_build_id_does_not_block_the_baseline(env: Env, tmp_path: Path) -> None:
    target = tmp_path / "scan.json"

    assert env.run(["--baseline-out", str(target)], env.site(page=page_html(None))) == 0
    assert json.loads(target.read_text(encoding="utf-8"))["api"] == EXPECTED_API


# --- running as a script ----------------------------------------------------------------


def run_script(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    # -S: no site-packages, so the scanner and everything it imports must be stdlib or repo code.
    return subprocess.run(
        [sys.executable, "-E", "-s", "-S", str(SCANNER), *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        timeout=30,
        check=False,
    )


def test_help_works_offline_without_installed_packages(tmp_path: Path) -> None:
    result = run_script("--help", cwd=tmp_path)

    assert result.returncode == 0, result.stderr
    for text in ("--json", "--compare", "--baseline-out", "kody wyjścia", "STOP", "D9"):
        assert text in result.stdout
    for text in ("incomplete", "Uwaga (niepełny wynik)", "Info:", str(scan_bundles.MAX_CHUNKS)):
        assert text in result.stdout
    for code in range(2, 8):
        assert re.search(rf"^\s+{code}\s", result.stdout, re.M), code


def test_config_is_imported_first_and_file_parses_on_old_python() -> None:
    """config's version check can only run if Python 3.9 compiles the scanner first."""
    source = SCANNER.read_text(encoding="utf-8")
    ast.parse(source, feature_version=(3, 9))
    body = ast.parse(source).body
    first = body[1] if isinstance(body[0], ast.Expr) else body[0]  # skip the docstring

    if isinstance(first, ast.ImportFrom):
        assert first.module == "config"
    else:
        assert isinstance(first, ast.Import)
        assert [alias.name for alias in first.names] == ["config"]
