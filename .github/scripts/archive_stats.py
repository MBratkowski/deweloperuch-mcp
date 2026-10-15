"""Archive the project's GitHub and PyPI statistics as CSV files (.github/workflows/stats.yml).

GitHub keeps a repository's traffic (views, clones, referrers, popular paths) for 14 days
and pypistats.org keeps daily downloads for about 180 days; run once a day, this keeps
them, with the release assets' download counters and the repository's stars, forks and
watchers. It reads api.github.com and pypistats.org only, never deweloperuch.pl, and
needs nothing but the standard library (no project environment)::

    STATS_TOKEN=... GITHUB_TOKEN=... python .github/scripts/archive_stats.py \\
        --repo MBratkowski/deweloperuch-mcp --out stats

- ``STATS_TOKEN``: reads the traffic, which needs the repository permission
  "Administration: read" (the Actions ``GITHUB_TOKEN`` gets 403 there). Unset or empty:
  the traffic is skipped with a warning.
- ``GITHUB_TOKEN`` (optional): sent to the public endpoints (releases, the repository),
  which also answer without one.
- ``--repo`` defaults to ``GITHUB_REPOSITORY``, which GitHub Actions sets.

Every source has its own file under ``--out`` (``SOURCES``); ``README.md`` there says what
each holds. A source that fails is reported as a warning and leaves its file as it was.
Warnings and errors are printed as GitHub Actions annotations; the script never prints a
token. Exit codes:

- 0: archived (sources that failed, if any, were warned about);
- 1: no source could be read, nothing archived;
- 2: wrong arguments (argparse);
- 3: ``STATS_TOKEN`` is set but the traffic endpoints refused it (HTTP 401 or 403); the
  other sources were archived, so the workflow commits them and then fails the run.
"""

import argparse
import csv
import datetime as dt
import http.client
import io
import json
import os
import re
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

USER_AGENT = "deweloperuch-mcp-stats (+https://github.com/MBratkowski/deweloperuch-mcp)"
GITHUB_API = "https://api.github.com/repos"
GITHUB_HEADERS = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
PYPI_DOWNLOADS = "https://pypistats.org/api/packages/deweloperuch-mcp/overall"
PAGE_SIZE = 100
MAX_PAGES = 50
"""Pages of releases read at most (5,000 releases), so a paging fault cannot loop forever."""
TIMEOUT = 30.0
REPOSITORY = re.compile(r"[A-Za-z0-9-]+/(?!\.\.?$)[A-Za-z0-9_.-]+")
"""``owner/name``: owners are letters, digits and hyphens; a name is never ``.`` or ``..``."""
TOKEN_HINT = "STATS_TOKEN must be a valid token with the repository permission Administration: read"
ARCHIVED, NOTHING_ARCHIVED, TOKEN_REFUSED = 0, 1, 3
FAILURES = (OSError, http.client.HTTPException, ValueError, KeyError, TypeError)
"""What makes one source fail: network errors (``URLError`` and ``HTTPError`` are
``OSError``), broken HTTP responses (``IncompleteRead``, ``BadStatusLine``), bodies that
are no JSON or not the expected shape, and archive files this script did not write
(``ArchiveError``)."""

Row = tuple[str, ...]
Fetch = Callable[[str, Mapping[str, str]], Any]
"""GET ``url`` with ``headers`` and return the decoded JSON body; raise on any failure."""


def fetch_json(
    url: str, headers: Mapping[str, str], opener: urllib.request.OpenerDirector | None = None
) -> Any:
    """GET ``url`` and decode its JSON body; an error status raises ``HTTPError``.

    ``Authorization`` is not sent again after a redirect (urllib would copy it to any host).
    That holds within api.github.com too: for a renamed repository GitHub redirects the old
    name, the token is dropped and the traffic is refused, so ``--repo`` must be the current
    name (in GitHub Actions ``GITHUB_REPOSITORY`` always is).
    """
    sent = dict(headers)
    token = sent.pop("Authorization", None)
    request = urllib.request.Request(url, headers=sent)
    if token is not None:
        request.add_unredirected_header("Authorization", token)
    with (opener or urllib.request.build_opener()).open(request, timeout=TIMEOUT) as response:
        return json.loads(response.read())


@dataclass(frozen=True)
class Apis:
    """GitHub's API for one repository and pypistats.org, with the tokens of the run."""

    fetch: Fetch
    repo: str
    github_token: str = field(repr=False)
    traffic_token: str = field(repr=False)

    def traffic(self, path: str) -> Any:
        return self._github(f"/traffic/{path}", self.traffic_token)

    def public(self, path: str) -> Any:
        return self._github(path, self.github_token)

    def pypi(self) -> Any:
        return self.fetch(PYPI_DOWNLOADS, {"Accept": "application/json", "User-Agent": USER_AGENT})

    def _github(self, path: str, token: str) -> Any:
        headers = {**GITHUB_HEADERS, "User-Agent": USER_AGENT}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return self.fetch(f"{GITHUB_API}/{self.repo}{path}", headers)


# --- the sources: what each request gives as rows of its file --------------------------------


def count(value: object) -> str:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{value!r} is not a count")
    return str(value)


def text(value: object) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{value!r} is not a text")
    return value


def utc_day(timestamp: object) -> str:
    """``2026-10-14T00:00:00Z`` -> ``2026-10-14`` (the day in UTC)."""
    return dt.datetime.fromisoformat(text(timestamp)).astimezone(dt.UTC).date().isoformat()


def daily(items: Any) -> list[Row]:
    return [
        (utc_day(item["timestamp"]), count(item["count"]), count(item["uniques"])) for item in items
    ]


def views(apis: Apis, _today: str) -> list[Row]:
    return daily(apis.traffic("views")["views"])


def clones(apis: Apis, _today: str) -> list[Row]:
    return daily(apis.traffic("clones")["clones"])


def referrers(apis: Apis, today: str) -> list[Row]:
    return [
        (today, text(item["referrer"]), count(item["count"]), count(item["uniques"]))
        for item in apis.traffic("popular/referrers")
    ]


def paths(apis: Apis, today: str) -> list[Row]:
    return [
        (
            today,
            text(item["path"]),
            text(item["title"]),
            count(item["count"]),
            count(item["uniques"]),
        )
        for item in apis.traffic("popular/paths")
    ]


def releases(apis: Apis, today: str) -> list[Row]:
    """Every asset of every published release (drafts stay private), page by page."""
    rows: list[Row] = []
    for page in range(1, MAX_PAGES + 1):
        batch = apis.public(f"/releases?per_page={PAGE_SIZE}&page={page}")
        rows += [
            (today, text(release["tag_name"]), text(asset["name"]), count(asset["download_count"]))
            for release in batch
            if not release["draft"]
            for asset in release["assets"]
        ]
        if len(batch) < PAGE_SIZE:
            return rows
    annotate("warning", f"releases: stopped after {MAX_PAGES} pages; later releases not archived")
    return rows


def repository(apis: Apis, today: str) -> list[Row]:
    found = apis.public("")
    # The watchers are subscribers_count; watchers_count is an old name of the stars.
    stars, forks, watchers = (
        count(found[name]) for name in ("stargazers_count", "forks_count", "subscribers_count")
    )
    return [(today, stars, forks, watchers)]


def downloads(apis: Apis, _today: str) -> list[Row]:
    return [
        (
            dt.date.fromisoformat(text(item["date"])).isoformat(),
            text(item["category"]),
            count(item["downloads"]),
        )
        for item in apis.pypi()["data"]
    ]


# --- the archive -----------------------------------------------------------------------------


class ArchiveError(ValueError):
    """A file of the archive that this script did not write."""


@dataclass(frozen=True)
class Source:
    """One request (or a paged series) and the CSV file it archives into.

    The first ``key`` columns identify a row and sort the file. A ``snapshot`` (first
    column ``captured``) is one capture per day: a rerun on the same day replaces that
    day's rows. Otherwise a fetched row replaces the archived row with the same key and
    the archived rows the API no longer returns stay.
    """

    name: str
    file: str
    columns: tuple[str, ...]
    key: int
    snapshot: bool
    read: Callable[[Apis, str], list[Row]]
    holds: str
    traffic: bool = False

    def store(self, out: Path, fetched: list[Row], today: str) -> bool:
        """Merge ``fetched`` into the file under ``out``; True when the file changed."""
        path = out / self.file
        return save(path, self.render(self.merge(self.load(path), fetched, today)))

    def merge(self, archived: list[Row], fetched: list[Row], today: str) -> list[Row]:
        if self.snapshot:
            kept = [row for row in archived if row[0] != today]
        else:
            fresh = {row[: self.key] for row in fetched}
            kept = [row for row in archived if row[: self.key] not in fresh]
        return sorted([*kept, *fetched], key=lambda row: row[: self.key])

    def load(self, path: Path) -> list[Row]:
        if not path.exists():
            return []
        try:
            with path.open(encoding="utf-8", newline="") as file:
                rows = [tuple(row) for row in csv.reader(file)]
        except (UnicodeDecodeError, csv.Error) as error:
            raise ArchiveError(f"{self.file}: {error}") from error
        if (
            not rows
            or rows[0] != self.columns
            or any(len(row) != len(self.columns) for row in rows)
        ):
            raise ArchiveError(f"{self.file} does not have the columns {','.join(self.columns)}")
        return rows[1:]

    def render(self, rows: list[Row]) -> str:
        buffer = io.StringIO()
        writer = csv.writer(buffer, lineterminator="\n")
        writer.writerow(self.columns)
        writer.writerows(rows)
        return buffer.getvalue()


DAILY = ("date", "count", "uniques")
WINDOW = "in the 14 days up to `captured`"
SOURCES = (
    Source(
        name="views",
        file="github/views.csv",
        columns=DAILY,
        key=1,
        snapshot=False,
        read=views,
        holds="Views of the repository's pages per day (all, unique visitors).",
        traffic=True,
    ),
    Source(
        name="clones",
        file="github/clones.csv",
        columns=DAILY,
        key=1,
        snapshot=False,
        read=clones,
        holds="Clones of the repository per day (all, unique cloners).",
        traffic=True,
    ),
    Source(
        name="referrers",
        file="github/referrers.csv",
        columns=("captured", "referrer", "count", "uniques"),
        key=2,
        snapshot=True,
        read=referrers,
        holds=f"The sites that sent the most visitors {WINDOW}.",
        traffic=True,
    ),
    Source(
        name="paths",
        file="github/paths.csv",
        columns=("captured", "path", "title", "count", "uniques"),
        key=2,
        snapshot=True,
        read=paths,
        holds=f"The most viewed pages of the repository {WINDOW}.",
        traffic=True,
    ),
    Source(
        name="releases",
        file="github/releases.csv",
        columns=("captured", "tag", "asset", "download_count"),
        key=3,
        snapshot=True,
        read=releases,
        holds="Downloads of each asset of each published release since its upload, as of "
        "`captured`.",
    ),
    Source(
        name="repository",
        file="github/repo.csv",
        columns=("captured", "stars", "forks", "watchers"),
        key=1,
        snapshot=True,
        read=repository,
        holds="The repository's stars, forks and watchers as of `captured`.",
    ),
    Source(
        name="pypi",
        file="pypi/downloads.csv",
        columns=("date", "category", "downloads"),
        key=2,
        snapshot=False,
        read=downloads,
        holds="Downloads of the PyPI package per day, `with_mirrors` and `without_mirrors` "
        "(pypistats.org).",
    ),
)

README = """\
# Project statistics

Written once a day by the `stats` workflow (`.github/workflows/stats.yml` and
`.github/scripts/archive_stats.py` on `main`); do not edit by hand. GitHub keeps a
repository's traffic for 14 days and pypistats.org daily downloads for about 180 days;
this branch keeps them.

All dates are UTC (`YYYY-MM-DD`); rows are sorted by their first columns. A file with a
`captured` column gets that day's capture on every run, and a rerun on the same day
replaces it. In the other files a later run replaces the rows of the dates it fetched
again (the latest day is partial until then) and keeps the older ones.

| File | Columns | Holds |
|---|---|---|
"""


def readme() -> str:
    return README + "".join(
        f"| `{source.file}` | `{','.join(source.columns)}` | {source.holds} |\n"
        for source in SOURCES
    )


def save(path: Path, content: str) -> bool:
    """Write ``content`` as UTF-8 unless the file holds it already; True when written."""
    data = content.encode("utf-8")
    if path.exists() and path.read_bytes() == data:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return True


def annotate(level: str, message: str) -> None:
    """Print a GitHub Actions annotation (``::warning::``, ``::error::``)."""
    escaped = message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    print(f"::{level}::{escaped}", flush=True)


def refused(error: Exception, source: Source) -> bool:
    """The traffic token was refused: GitHub answered 401 or 403 to a traffic request."""
    return source.traffic and isinstance(error, urllib.error.HTTPError) and error.code in (401, 403)


def describe(error: Exception, source: Source) -> str:
    if isinstance(error, urllib.error.HTTPError):
        hint = f" ({TOKEN_HINT})" if refused(error, source) else ""
        return f"HTTP {error.code} {error.reason}{hint}"
    if isinstance(error, urllib.error.URLError):
        return f"no response ({error.reason})"
    if isinstance(error, OSError):
        return f"{type(error).__name__}: {error}"
    if isinstance(error, http.client.HTTPException):
        return f"broken HTTP response ({type(error).__name__})"
    if isinstance(error, ArchiveError):
        return f"unexpected archive ({error})"
    return f"unexpected response ({type(error).__name__}: {error})"


def archive(apis: Apis, out: Path, today: str) -> tuple[int, bool]:
    """Archive every source under ``out``; return how many could be read and whether the
    traffic token was refused."""
    archived, token_refused = 0, False
    for source in SOURCES:
        if source.traffic and not apis.traffic_token:
            continue
        try:
            fetched = source.read(apis, today)
            changed = source.store(out, fetched, today)
        except FAILURES as error:
            token_refused = token_refused or refused(error, source)
            said = describe(error, source)
            annotate("warning", f"{source.name}: {said}; {source.file} left as it was")
            continue
        archived += 1
        state = "updated" if changed else "unchanged"
        print(f"{source.name}: {len(fetched)} rows, {source.file} {state}")
    return archived, token_refused


def arguments(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Archive the project's GitHub traffic, release downloads, repository "
        "counters and PyPI downloads as CSV files (reads api.github.com and pypistats.org)."
    )
    parser.add_argument(
        "--repo",
        default=os.environ.get("GITHUB_REPOSITORY"),
        help="owner/name of the GitHub repository (default: $GITHUB_REPOSITORY)",
    )
    parser.add_argument(
        "--out", type=Path, required=True, help="the archive (a checkout of the stats branch)"
    )
    args = parser.parse_args(argv)
    if not args.repo or not REPOSITORY.fullmatch(args.repo):
        parser.error("--repo owner/name is required (or GITHUB_REPOSITORY)")
    return args


def main(
    argv: Sequence[str] | None = None, *, fetch: Fetch = fetch_json, today: dt.date | None = None
) -> int:
    args = arguments(argv)
    day = (today or dt.datetime.now(dt.UTC).date()).isoformat()
    apis = Apis(
        fetch, args.repo, os.environ.get("GITHUB_TOKEN", ""), os.environ.get("STATS_TOKEN", "")
    )
    if not apis.traffic_token:
        annotate("warning", f"STATS_TOKEN is not set: GitHub traffic skipped ({TOKEN_HINT})")
    save(args.out / "README.md", readme())
    archived, token_refused = archive(apis, args.out, day)
    if archived == 0:
        annotate("error", "No source could be read: nothing archived")
        return NOTHING_ARCHIVED
    if token_refused:
        annotate("error", f"GitHub refused STATS_TOKEN; the rest was archived ({TOKEN_HINT})")
        return TOKEN_REFUSED
    return ARCHIVED


if __name__ == "__main__":
    raise SystemExit(main())
