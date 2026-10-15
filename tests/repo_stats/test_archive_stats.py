"""The daily archive of the project's GitHub and PyPI statistics
(.github/scripts/archive_stats.py, run by .github/workflows/stats.yml).

Offline: the APIs are ``StatsApis``, answering with real responses from
tests/fixtures/repo_stats/, and the urllib transport answers from memory. The archive is
written to the test's temporary directory. Rows in the archive's own CSV format are
written by hand where a test needs an earlier archive.
"""

import ast
import datetime as dt
import http.client
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest

import archive_stats
from support.fakes.clocks import frozen_datetime
from support.fakes.probe import InMemoryHTTPS
from support.fakes.stats_apis import (
    CLONES,
    PATHS,
    PUBLIC,
    PYPI,
    REFERRERS,
    RELEASES,
    REPOSITORY,
    REPOSITORY_URL,
    TRAFFIC,
    VIEWS,
    StatsApis,
    fixture,
    http_error,
)
from support.paths import REPO_STATS_FIXTURES, STATS_SCRIPT

TODAY = dt.date(2026, 10, 15)
TOKENS = {"STATS_TOKEN": "stats-token-value", "GITHUB_TOKEN": "github-token-value"}
USER_AGENT = "deweloperuch-mcp-stats (+https://github.com/MBratkowski/deweloperuch-mcp)"
CSV_FILES = [
    "github/clones.csv",
    "github/paths.csv",
    "github/referrers.csv",
    "github/releases.csv",
    "github/repo.csv",
    "github/views.csv",
    "pypi/downloads.csv",
]
FILE_OF = {
    VIEWS: "github/views.csv",
    CLONES: "github/clones.csv",
    REFERRERS: "github/referrers.csv",
    PATHS: "github/paths.csv",
    RELEASES: "github/releases.csv",
    REPOSITORY_URL: "github/repo.csv",
    PYPI: "pypi/downloads.csv",
}
PREVIOUS = {
    VIEWS: "date,count,uniques\n2026-09-30,7,3\n",
    CLONES: "date,count,uniques\n2026-09-30,2,1\n",
    REFERRERS: "captured,referrer,count,uniques\n2026-10-14,t.co,20,18\n",
    PATHS: (
        "captured,path,title,count,uniques\n"
        "2026-10-14,/MBratkowski/deweloperuch-mcp,Overview,30,25\n"
    ),
    RELEASES: "captured,tag,asset,download_count\n2026-10-14,v0.1.1,server.json,0\n",
    REPOSITORY_URL: "captured,stars,forks,watchers\n2026-10-14,12,0,1\n",
    PYPI: "date,category,downloads\n2026-10-13,with_mirrors,5\n",
}
"""An earlier archive of each source, valid (a run merges into it), by the source's URL."""
VIEWS_401 = (REPO_STATS_FIXTURES / "views_401.json").read_bytes()
REFUSED = "STATS_TOKEN must be a valid token with the repository permission Administration: read"


@pytest.fixture(autouse=True)
def environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Both tokens set, and no repository from the environment (GitHub Actions sets one)."""
    for name, value in TOKENS.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)


def run(out: Path, apis: StatsApis) -> int:
    return archive_stats.main(["--repo", REPOSITORY, "--out", str(out)], fetch=apis, today=TODAY)


def names(out: Path) -> list[str]:
    """The paths of the archive's files, sorted."""
    return sorted(path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file())


def archive(out: Path) -> dict[str, str]:
    """Every file of the archive by its path, decoded as UTF-8 (line endings kept)."""
    return {name: (out / name).read_bytes().decode("utf-8") for name in names(out)}


def write(out: Path, name: str, text: str) -> None:
    path = out / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))


# --- what a run archives ---------------------------------------------------------------------


def test_a_run_archives_every_source_from_the_real_responses(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert run(tmp_path, StatsApis()) == 0

    files = archive(tmp_path)
    assert list(files) == ["README.md", *CSV_FILES]
    assert files["github/views.csv"] == (
        "date,count,uniques\n"
        + "".join(f"2026-10-{day:02},0,0\n" for day in range(1, 14))
        + "2026-10-14,92,40\n"
    )
    assert files["github/clones.csv"].startswith("date,count,uniques\n2026-10-01,0,0\n")
    assert files["github/clones.csv"].endswith("2026-10-13,0,0\n2026-10-14,103,46\n")
    assert files["github/referrers.csv"] == (
        "captured,referrer,count,uniques\n"
        "2026-10-15,Google,1,1\n"
        "2026-10-15,github.com,6,1\n"
        "2026-10-15,t.co,26,24\n"
    )
    paths = files["github/paths.csv"].splitlines()
    assert paths[:3] == [
        "captured,path,title,count,uniques",
        "2026-10-15,/MBratkowski/deweloperuch-mcp,Overview,40,31",
        "2026-10-15,/MBratkowski/deweloperuch-mcp/actions,/actions,1,1",
    ]
    assert len(paths) == 1 + 10
    assert files["github/releases.csv"] == (
        "captured,tag,asset,download_count\n"
        "2026-10-15,v0.1.0,deweloperuch-mcp-0.1.0.mcpb,0\n"
        "2026-10-15,v0.1.0,deweloperuch_mcp-0.1.0-py3-none-any.whl,0\n"
        "2026-10-15,v0.1.0,deweloperuch_mcp-0.1.0.tar.gz,0\n"
        "2026-10-15,v0.1.1,deweloperuch-mcp-0.1.1.mcpb,12\n"
        "2026-10-15,v0.1.1,deweloperuch_mcp-0.1.1-py3-none-any.whl,0\n"
        "2026-10-15,v0.1.1,deweloperuch_mcp-0.1.1.tar.gz,0\n"
        "2026-10-15,v0.1.1,server.json,1\n"
    )
    # Watchers are subscribers_count (16 is stargazers_count, also named watchers_count).
    assert files["github/repo.csv"] == "captured,stars,forks,watchers\n2026-10-15,16,0,1\n"
    assert files["pypi/downloads.csv"] == (
        "date,category,downloads\n2026-10-14,with_mirrors,260\n2026-10-14,without_mirrors,110\n"
    )
    assert "::" not in capsys.readouterr().out  # no warning, no error


def test_requests_go_to_github_and_pypistats_only_with_an_honest_user_agent(
    tmp_path: Path,
) -> None:
    apis = StatsApis()

    run(tmp_path, apis)

    assert apis.urls == [*TRAFFIC, *PUBLIC]
    assert {headers["User-Agent"] for _, headers in apis.requests} == {USER_AGENT}
    github = {url: headers for url, headers in apis.requests if url != PYPI}
    assert all(
        headers["Accept"] == "application/vnd.github+json"
        and headers["X-GitHub-Api-Version"] == "2022-11-28"
        for headers in github.values()
    )
    # The traffic token only where it is needed; pypistats.org gets no token at all.
    assert {url: headers["Authorization"] for url, headers in github.items()} == {
        **dict.fromkeys(TRAFFIC, "Bearer stats-token-value"),
        RELEASES: "Bearer github-token-value",
        REPOSITORY_URL: "Bearer github-token-value",
    }
    assert "Authorization" not in dict(apis.requests)[PYPI]


def test_the_public_endpoints_are_read_without_a_token_when_github_token_is_unset(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("GITHUB_TOKEN")
    apis = StatsApis()

    assert run(tmp_path, apis) == 0

    assert [url for url, headers in apis.requests if "Authorization" not in headers] == list(PUBLIC)


def test_releases_are_read_page_by_page_and_drafts_are_left_out(tmp_path: Path) -> None:
    released = fixture("releases.json")
    full_page = [{**released[0], "tag_name": f"v0.0.{n}"} for n in range(100)]
    draft = {**released[0], "tag_name": "v9.9.9", "draft": True}
    second_page = f"{REPOSITORY_URL}/releases?per_page=100&page=2"
    apis = StatsApis({RELEASES: full_page, second_page: [draft, *released]})

    run(tmp_path, apis)

    rows = archive(tmp_path)["github/releases.csv"].splitlines()[1:]
    assert len(rows) == 100 * 4 + 7  # v0.1.1 has 4 assets, v0.1.0 3
    assert not any(",v9.9.9," in row for row in rows)
    assert [url for url in apis.urls if "/releases" in url] == [RELEASES, second_page]


def test_the_archive_says_what_each_file_holds(tmp_path: Path) -> None:
    run(tmp_path, StatsApis())

    readme = archive(tmp_path)["README.md"]

    assert all(f"`{name}`" in readme for name in CSV_FILES)
    assert "UTC" in readme


# --- merging with the archive ---------------------------------------------------------------


def test_a_second_run_with_the_same_responses_changes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    run(tmp_path, StatsApis())
    first = archive(tmp_path)
    capsys.readouterr()

    assert run(tmp_path, StatsApis()) == 0

    assert archive(tmp_path) == first
    said = capsys.readouterr().out
    assert said.count("unchanged") == len(CSV_FILES)
    assert "updated" not in said


def test_daily_counts_replace_the_same_date_and_keep_dates_the_api_no_longer_returns(
    tmp_path: Path,
) -> None:
    write(tmp_path, "github/views.csv", "date,count,uniques\n2026-10-14,50,20\n2026-09-30,7,3\n")
    write(
        tmp_path,
        "pypi/downloads.csv",
        "date,category,downloads\n2026-10-14,with_mirrors,100\n2026-10-13,without_mirrors,5\n",
    )

    run(tmp_path, StatsApis())

    files = archive(tmp_path)
    views = files["github/views.csv"].splitlines()
    assert views[:3] == ["date,count,uniques", "2026-09-30,7,3", "2026-10-01,0,0"]
    assert views[-1] == "2026-10-14,92,40"  # the partial day of the earlier run corrected
    assert len(views) == 1 + 1 + 14
    assert files["pypi/downloads.csv"] == (
        "date,category,downloads\n"
        "2026-10-13,without_mirrors,5\n"
        "2026-10-14,with_mirrors,260\n"
        "2026-10-14,without_mirrors,110\n"
    )


def test_a_rerun_on_the_same_day_replaces_that_days_capture_and_keeps_earlier_ones(
    tmp_path: Path,
) -> None:
    write(
        tmp_path,
        "github/referrers.csv",
        "captured,referrer,count,uniques\n"
        "2026-10-15,example.com,9,9\n"  # gone from today's top referrers
        "2026-10-15,t.co,1,1\n"
        "2026-10-14,news.ycombinator.com,4,4\n",
    )
    write(tmp_path, "github/repo.csv", "captured,stars,forks,watchers\n2026-10-15,3,0,1\n")

    run(tmp_path, StatsApis())

    files = archive(tmp_path)
    assert files["github/referrers.csv"] == (
        "captured,referrer,count,uniques\n"
        "2026-10-14,news.ycombinator.com,4,4\n"
        "2026-10-15,Google,1,1\n"
        "2026-10-15,github.com,6,1\n"
        "2026-10-15,t.co,26,24\n"
    )
    assert files["github/repo.csv"] == "captured,stars,forks,watchers\n2026-10-15,16,0,1\n"


def test_an_empty_capture_still_replaces_the_days_rows(tmp_path: Path) -> None:
    write(
        tmp_path, "github/referrers.csv", "captured,referrer,count,uniques\n2026-10-15,t.co,1,1\n"
    )

    run(tmp_path, StatsApis({REFERRERS: []}))

    assert archive(tmp_path)["github/referrers.csv"] == "captured,referrer,count,uniques\n"


def test_files_are_utf8_csv_with_lf_endings_and_quoted_fields_survive_a_rerun(
    tmp_path: Path,
) -> None:
    earlier = (
        "captured,path,title,count,uniques\n"
        '2026-10-14,/MBratkowski/deweloperuch-mcp/issues/1,"Błąd, ""cytat""",2,1\n'
    )
    write(tmp_path, "github/paths.csv", earlier)

    run(tmp_path, StatsApis())
    run(tmp_path, StatsApis())

    files = archive(tmp_path)
    assert files["github/paths.csv"].startswith(earlier)
    assert not any("\r" in files[name] for name in CSV_FILES)


# --- failures -------------------------------------------------------------------------------


@pytest.mark.parametrize("token", [None, ""], ids=["unset", "empty secret"])
def test_without_stats_token_the_traffic_is_skipped_with_a_warning(
    token: str | None,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if token is None:
        monkeypatch.delenv("STATS_TOKEN")
    else:
        monkeypatch.setenv("STATS_TOKEN", token)  # a missing secret reaches the job as ""
    apis = StatsApis()

    assert run(tmp_path, apis) == 0

    assert apis.urls == list(PUBLIC)
    assert names(tmp_path) == [
        "README.md",
        "github/releases.csv",
        "github/repo.csv",
        "pypi/downloads.csv",
    ]
    warnings = [line for line in capsys.readouterr().out.splitlines() if line.startswith("::")]
    assert len(warnings) == 1
    assert warnings[0].startswith("::warning::STATS_TOKEN is not set")


def test_the_previous_archives_of_these_tests_are_valid(tmp_path: Path) -> None:
    """So a test that finds one unchanged shows that its source failed, not the file."""
    for url, content in PREVIOUS.items():
        write(tmp_path, FILE_OF[url], content)

    assert run(tmp_path, StatsApis()) == 0

    files = archive(tmp_path)
    assert all(
        files[FILE_OF[url]].startswith(content) and files[FILE_OF[url]] != content
        for url, content in PREVIOUS.items()
    )


@pytest.mark.parametrize(
    ("url", "failure", "said"),
    [
        (RELEASES, http_error(RELEASES, 403, "Forbidden"), "releases: HTTP 403 Forbidden;"),
        (
            VIEWS,
            http_error(VIEWS, 503, "Service Unavailable"),
            "views: HTTP 503 Service Unavailable;",
        ),
        (RELEASES, http_error(RELEASES, 429, "Too Many"), "releases: HTTP 429 Too Many;"),
        (PYPI, urllib.error.URLError(TimeoutError("timed out")), "pypi: no response (timed out);"),
        (
            REPOSITORY_URL,
            TimeoutError("The read operation timed out"),
            "repository: TimeoutError: The read operation timed out;",
        ),
        (
            RELEASES,
            http.client.IncompleteRead(b'[{"url":', 9000),
            "releases: broken HTTP response (IncompleteRead);",
        ),
        (
            CLONES,
            {"message": "Not Found"},
            "clones: unexpected response (KeyError: 'clones');",
        ),
        (
            REFERRERS,
            [{"referrer": "t.co"}],
            "referrers: unexpected response (KeyError: 'count');",
        ),
        (
            PATHS,
            [{"path": "/x", "title": None, "count": 1, "uniques": 1}],
            "paths: unexpected response (TypeError: None is not a text);",
        ),
        (
            PYPI,
            {"data": [{"date": "x", "category": "with_mirrors", "downloads": 1}]},
            "pypi: unexpected response (ValueError: Invalid isoformat string: 'x');",
        ),
        (
            REPOSITORY_URL,
            {"stargazers_count": "16", "forks_count": 0, "subscribers_count": 1},
            "repository: unexpected response (TypeError: '16' is not a count);",
        ),
    ],
    ids=[
        "403 public",
        "503 traffic",  # only 401 and 403 refuse the token
        "429",
        "no response",
        "timeout",
        "incomplete read",
        "error body",
        "missing field",
        "no title",
        "date",
        "count",
    ],
)
def test_a_failing_source_keeps_its_file_and_the_others_are_archived(
    url: str,
    failure: object,
    said: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    write(tmp_path, FILE_OF[url], PREVIOUS[url])

    assert run(tmp_path, StatsApis({url: failure})) == 0

    files = archive(tmp_path)
    assert files[FILE_OF[url]] == PREVIOUS[url]
    assert list(files) == ["README.md", *CSV_FILES]
    out = capsys.readouterr().out
    assert [line for line in out.splitlines() if line.startswith("::")] == [
        f"::warning::{said} {FILE_OF[url]} left as it was"
    ]
    assert not any(token in out for token in TOKENS.values())


@pytest.mark.parametrize(
    "failing",
    [
        {VIEWS: http_error(VIEWS, 401, "Unauthorized", VIEWS_401)},
        {PATHS: http_error(PATHS, 403, "Forbidden")},
        {url: http_error(url, 403, "Forbidden") for url in TRAFFIC},
        # A later failure of another kind does not undo the refusal.
        {
            VIEWS: http_error(VIEWS, 401, "Unauthorized", VIEWS_401),
            PYPI: http_error(PYPI, 503, "Service Unavailable"),
        },
    ],
    ids=["401", "403", "every traffic request 403", "401, then pypi 503"],
)
def test_a_refused_stats_token_archives_the_rest_and_fails_with_3(
    failing: dict[str, object], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    for url in failing:
        write(tmp_path, FILE_OF[url], PREVIOUS[url])

    assert run(tmp_path, StatsApis(failing)) == 3

    files = archive(tmp_path)
    assert {url: files[FILE_OF[url]] for url in failing} == {url: PREVIOUS[url] for url in failing}
    assert list(files) == ["README.md", *CSV_FILES]
    out = capsys.readouterr().out
    *warnings, error = [line for line in out.splitlines() if line.startswith("::")]
    assert len(warnings) == len(failing)
    # The hint goes with the refused traffic requests only (here: every failing one but pypi).
    assert [f"({REFUSED}); github/" in warning for warning in warnings] == [
        url != PYPI for url in failing
    ]
    assert error == f"::error::GitHub refused STATS_TOKEN; the rest was archived ({REFUSED})"
    assert not any(token in out for token in TOKENS.values())


@pytest.mark.parametrize(
    ("content", "said"),
    [
        (b"date,views\n2026-10-01,3\n", "github/views.csv does not have the columns"),
        (b"date,category,downloads\n2026-10-01,a,3\n", "github/views.csv does not have the"),
        (b"date,count,uniques\n2026-10-01,3\n", "github/views.csv does not have the columns"),
        (b"", "github/views.csv does not have the columns date,count,uniques"),
        (b"date,count,uniques\n\xff\xfe\n", "github/views.csv: 'utf-8' codec"),
        (b"x" * 200_000, "github/views.csv: field larger than field limit"),
    ],
    ids=["other columns", "other columns, same count", "short row", "empty", "not utf-8", "csv"],
)
def test_an_archive_file_the_script_did_not_write_is_left_alone(
    content: bytes, said: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "github").mkdir()
    (tmp_path / "github/views.csv").write_bytes(content)

    assert run(tmp_path, StatsApis()) == 0

    assert (tmp_path / "github/views.csv").read_bytes() == content
    assert f"::warning::views: unexpected archive ({said}" in capsys.readouterr().out
    assert names(tmp_path) == ["README.md", *CSV_FILES]


@pytest.mark.parametrize(
    ("stats_token", "traffic_status"),
    [("stats-token-value", 503), ("stats-token-value", 401), ("", 503)],
    ids=["token", "token refused too", "no token"],
)
def test_when_no_source_can_be_read_the_run_fails_with_1(
    stats_token: str,
    traffic_status: int,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("STATS_TOKEN", stats_token)
    failing = {
        **{url: http_error(url, traffic_status, "Refused or down") for url in TRAFFIC},
        **{url: http_error(url, 503, "Service Unavailable") for url in PUBLIC},
    }

    assert run(tmp_path, StatsApis(failing)) == 1

    out = capsys.readouterr().out
    assert out.splitlines()[-1] == "::error::No source could be read: nothing archived"
    assert names(tmp_path) == ["README.md"]
    assert not any(token in out for token in TOKENS.values())


def test_releases_stop_at_the_page_cap_with_a_warning(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(archive_stats, "MAX_PAGES", 2)
    release = fixture("releases.json")[0]  # 4 assets
    pages = {
        f"{REPOSITORY_URL}/releases?per_page=100&page={page}": [
            {**release, "tag_name": f"v{page}.0.{n}"} for n in range(100)
        ]
        for page in (1, 2)
    }
    apis = StatsApis(pages)

    assert run(tmp_path, apis) == 0

    assert [url for url in apis.urls if "/releases" in url] == list(pages)
    assert len(archive(tmp_path)["github/releases.csv"].splitlines()) == 1 + 2 * 100 * 4
    warning = "::warning::releases: stopped after 2 pages; later releases not archived"
    assert warning in capsys.readouterr().out.splitlines()


def test_annotations_stay_on_one_line(capsys: pytest.CaptureFixture[str]) -> None:
    archive_stats.annotate("warning", "50% read\r\nthen nothing")

    assert capsys.readouterr().out == "::warning::50%25 read%0D%0Athen nothing\n"


def test_the_day_of_a_run_is_the_day_in_utc(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 03:30 UTC on 2026-10-15 is still 2026-10-14 on a machine five hours behind UTC.
    instant = dt.datetime(2026, 10, 15, 3, 30, tzinfo=dt.UTC)
    monkeypatch.setattr(archive_stats, "dt", frozen_datetime(instant, dt.timedelta(hours=-5)))

    argv = ["--repo", REPOSITORY, "--out", str(tmp_path)]
    assert archive_stats.main(argv, fetch=StatsApis()) == 0

    assert archive(tmp_path)["github/repo.csv"] == (
        "captured,stars,forks,watchers\n2026-10-15,16,0,1\n"
    )


# --- the command line and the transport -----------------------------------------------------


@pytest.mark.parametrize(
    "repo",
    [
        [],
        ["--repo", "deweloperuch-mcp"],
        ["--repo", "a/b/c"],
        ["--repo", "../deweloperuch-mcp"],
        ["--repo", "MBratkowski/.."],
        ["--repo", "MBratkowski/."],
    ],
    ids=["missing", "no owner", "path", "dot-dot owner", "dot-dot name", "dot name"],
)
def test_the_repository_is_required_as_owner_slash_name(
    repo: list[str], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    apis = StatsApis()

    with pytest.raises(SystemExit) as exited:
        archive_stats.main([*repo, "--out", str(tmp_path)], fetch=apis, today=TODAY)

    assert exited.value.code == 2
    assert "--repo" in capsys.readouterr().err
    assert apis.requests == []
    assert names(tmp_path) == []


def test_the_repository_defaults_to_github_repository(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("GITHUB_REPOSITORY", REPOSITORY)
    apis = StatsApis()

    assert archive_stats.main(["--out", str(tmp_path)], fetch=apis, today=TODAY) == 0

    assert apis.urls == [*TRAFFIC, *PUBLIC]


def test_fetch_json_sends_the_headers_and_decodes_the_body() -> None:
    handler = InMemoryHTTPS((200, {}, (REPO_STATS_FIXTURES / "views.json").read_bytes()))
    headers = {"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"}

    body = archive_stats.fetch_json(VIEWS, headers, urllib.request.build_opener(handler))

    assert body == fixture("views.json")
    [request] = handler.requests
    assert request.full_url == VIEWS
    assert request.get_header("User-agent") == USER_AGENT  # not urllib's own
    assert request.timeout == 30.0


def test_fetch_json_does_not_send_the_token_after_a_redirect() -> None:
    handler = InMemoryHTTPS(
        (302, {"Location": "https://elsewhere.example/moved"}, b""), (200, {}, b"{}")
    )
    headers = {"User-Agent": USER_AGENT, "Authorization": "Bearer stats-token-value"}

    archive_stats.fetch_json(VIEWS, headers, urllib.request.build_opener(handler))

    first, redirected = handler.requests
    assert first.get_header("Authorization") == "Bearer stats-token-value"
    assert redirected.full_url == "https://elsewhere.example/moved"
    assert redirected.get_header("Authorization") is None
    assert redirected.get_header("User-agent") == USER_AGENT


def test_the_tokens_are_not_in_the_repr_of_the_apis() -> None:
    apis = archive_stats.Apis(StatsApis(), REPOSITORY, "github-token-value", "stats-token-value")

    assert not any(token in repr(apis) for token in TOKENS.values())


def test_fetch_json_raises_on_an_error_status() -> None:
    body = (REPO_STATS_FIXTURES / "views_401.json").read_bytes()
    handler = InMemoryHTTPS((401, {"Content-Type": "application/json"}, body))

    with pytest.raises(urllib.error.HTTPError) as raised:
        archive_stats.fetch_json(VIEWS, {}, urllib.request.build_opener(handler))

    assert raised.value.code == 401


def test_the_script_uses_only_the_standard_library() -> None:
    """It runs on the GitHub runner without the project's environment."""
    tree = ast.parse(STATS_SCRIPT.read_text(encoding="utf-8"))
    imported = {
        name.split(".")[0]
        for node in ast.walk(tree)
        for name in (
            [alias.name for alias in node.names]
            if isinstance(node, ast.Import)
            else [node.module or ""]
            if isinstance(node, ast.ImportFrom)
            else []
        )
    }

    assert imported <= sys.stdlib_module_names


def test_the_script_runs_on_its_own() -> None:
    finished = subprocess.run(
        [sys.executable, "-I", str(STATS_SCRIPT), "--help"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert finished.returncode == 0, finished.stderr
    assert "--repo" in finished.stdout
