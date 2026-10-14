"""The site the scanner reads, in memory: its pages, the webpack runtime and the chunks
(with their server actions), answered as the service would.
"""

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

import scan_bundles
from deweloperuch_mcp import identity
from http_common import Response
from support.checks.locks import lock_is_held

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


@dataclass
class FakeScannedSite:
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
