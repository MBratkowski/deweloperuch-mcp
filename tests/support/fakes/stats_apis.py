"""Stand-in of the APIs the statistics archive reads (``archive_stats.Fetch``): every URL
answers with its real response from tests/fixtures/repo_stats/ or with the error a test
gives it, and every request is recorded.
"""

import copy
import email.message
import io
import json
import urllib.error
from collections.abc import Mapping
from typing import Any

from support.paths import REPO_STATS_FIXTURES

REPOSITORY = "MBratkowski/deweloperuch-mcp"
REPOSITORY_URL = f"https://api.github.com/repos/{REPOSITORY}"
VIEWS = f"{REPOSITORY_URL}/traffic/views"
CLONES = f"{REPOSITORY_URL}/traffic/clones"
REFERRERS = f"{REPOSITORY_URL}/traffic/popular/referrers"
PATHS = f"{REPOSITORY_URL}/traffic/popular/paths"
RELEASES = f"{REPOSITORY_URL}/releases?per_page=100&page=1"
PYPI = "https://pypistats.org/api/packages/deweloperuch-mcp/overall"

TRAFFIC = (VIEWS, CLONES, REFERRERS, PATHS)
PUBLIC = (RELEASES, REPOSITORY_URL, PYPI)
"""The sources that need no traffic token, in the order the script reads them."""
FIXTURE_OF = {
    VIEWS: "views.json",
    CLONES: "clones.json",
    REFERRERS: "referrers.json",
    PATHS: "paths.json",
    RELEASES: "releases.json",
    REPOSITORY_URL: "repo.json",
    PYPI: "pypistats_overall.json",
}


def fixture(name: str) -> Any:
    """The decoded body of tests/fixtures/repo_stats/``name``."""
    return json.loads((REPO_STATS_FIXTURES / name).read_bytes())


def http_error(url: str, status: int, reason: str, body: bytes = b"") -> urllib.error.HTTPError:
    """What urllib raises for an error status."""
    return urllib.error.HTTPError(url, status, reason, email.message.Message(), io.BytesIO(body))


class StatsApis:
    """GitHub and pypistats.org answering with the real responses; ``answers`` replaces
    some of them (a body or an exception to raise) or adds URLs."""

    def __init__(self, answers: Mapping[str, object] | None = None) -> None:
        self.answers: dict[str, object] = {url: fixture(name) for url, name in FIXTURE_OF.items()}
        self.answers.update(answers or {})
        self.requests: list[tuple[str, dict[str, str]]] = []

    def __call__(self, url: str, headers: Mapping[str, str]) -> Any:
        self.requests.append((url, dict(headers)))
        if url not in self.answers:  # not an error the script may tolerate: the test is wrong
            raise AssertionError(f"unexpected request: {url}")
        answer = self.answers[url]
        if isinstance(answer, BaseException):
            raise answer
        return copy.deepcopy(answer)

    @property
    def urls(self) -> list[str]:
        return [url for url, _ in self.requests]
