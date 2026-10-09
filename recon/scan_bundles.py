"""Scan deweloperuch.pl JS bundles for data-layer entry points.

Downloads the HTML of a few representative pages, collects every Next.js chunk they
reference (plus lazily loaded chunks listed in the webpack runtime), and prints:
  - every `/api/...` path literal found in client code,
  - every Next.js Server Action (id + exported name).

Use it to detect drift after a site deploy (new/removed endpoints, rotated action ids).
Stdlib only. Respects robots.txt Crawl-delay (1 s between page requests).

    python3 recon/scan_bundles.py [--json]
"""

import json
import re
import sys
import time
import urllib.request

BASE = "https://deweloperuch.pl"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"

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

CHUNK_RE = re.compile(r"/_next/static/chunks/[A-Za-z0-9_./\[\]%()-]+\.js")
API_RE = re.compile(r"""["'`](/api/[^"'`]*)""")
ACTION_RE = re.compile(
    r'createServerReference\)\("([0-9a-f]{40,})",[\w$]+\.callServer,void 0,[\w$]+\.findSourceMapURL,"(\w+)"'
)
# webpack runtime: r.u=e=> ... "static/chunks/"+({id:"name"})[e]||e)+"."+({id:"hash"})[e]+".js"
LAZY_NAMES_RE = re.compile(r'"static/chunks/"\+\(\((\{[^}]*\})\)\[e\]\|\|e\)\+"\."\+\((\{[^}]*\})\)\[e\]')
LAZY_FIXED_RE = re.compile(r'"(static/chunks/[A-Za-z0-9_.-]+\.js)"')


def get(path: str) -> str:
    req = urllib.request.Request(BASE + path, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8", errors="replace")


def js_object(src: str) -> dict:
    # minified object literal with numeric keys -> JSON
    return json.loads(re.sub(r"([{,])(\d+):", r'\1"\2":', src))


def lazy_chunks(runtime_js: str) -> set[str]:
    out = {"/_next/" + p for p in LAZY_FIXED_RE.findall(runtime_js)}
    m = LAZY_NAMES_RE.search(runtime_js)
    if m:
        names, hashes = js_object(m.group(1)), js_object(m.group(2))
        for cid, h in hashes.items():
            out.add(f"/_next/static/chunks/{names.get(cid, cid)}.{h}.js")
    return out


def main() -> None:
    chunks: set[str] = set()
    for i, page in enumerate(PAGES):
        if i:
            time.sleep(1)
        chunks |= set(CHUNK_RE.findall(get(page)))

    runtime = next((c for c in chunks if "/webpack-" in c), None)
    if runtime:
        chunks |= lazy_chunks(get(runtime))

    apis: dict[str, set[str]] = {}
    actions: dict[str, str] = {}
    for c in sorted(chunks):
        js = get(c)
        for path in API_RE.findall(js):
            apis.setdefault(path, set()).add(c.rsplit("/", 1)[-1])
        for action_id, name in ACTION_RE.findall(js):
            actions[name] = action_id

    if "--json" in sys.argv:
        print(json.dumps({"chunks": len(chunks), "api": sorted(apis), "actions": actions}, indent=2))
        return
    print(f"# chunks scanned: {len(chunks)}\n\n## /api paths")
    for path in sorted(apis):
        print(f"  {path}")
    print("\n## server actions")
    for name, action_id in sorted(actions.items()):
        print(f"  {name:32} {action_id}")


if __name__ == "__main__":
    main()
