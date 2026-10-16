"""Characterization ("golden") checks: what the CLI and the MCP tools answer, recorded.

Every case of ``tests/characterization/cli/`` and
``tests/characterization/mcp/`` is one file in
``tests/golden/<surface>/<case>.json``: the exit code or the tool result, the output as it
is (texts, JSON, messages, log lines) and the requests sent to the mocked service (method,
URL with its query, the ``RSC`` and ``Accept`` headers). The files were recorded on the
code before the D13 refactor, so a refactor that changes any output, any message, any
exit code or any request URL fails here.

After an intended change of the output (and only then):

    DEWELOPERUCH_UPDATE_GOLDEN=1 uv run pytest tests/characterization

rewrites the files of the cases that ran; ``git diff tests/golden`` shows which cases
moved and how. See tests/golden/README.md.

Volatile values (times, PIDs, seconds left of a pause, temporary paths) are replaced by
placeholders (``scrub``) before comparing; nothing else is.
"""

import json
import os
import re
from typing import Any

import respx

from support.paths import GOLDEN

UPDATE_GOLDEN = "DEWELOPERUCH_UPDATE_GOLDEN"


_TIME = re.compile(r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[+-]\d{2}:\d{2}|Z)?")
_PID = re.compile(r"PID \d+")
_SECONDS_LEFT = re.compile(r"\(za \d+ s\)")
_PAUSE_LEFT = re.compile(r"trwa jeszcze ok\. \d+ s")
_JSON_NUMBERS = re.compile(r'"(pid|seconds_left)": [0-9.eE+-]+')


# Unlinking a directory differs between POSIX and Windows; keep only that an OS error happened.
_OS_ERROR = re.compile(r"\[(?:Errno|WinError) \d+\] [^:'\n]+")


def scrub(text: str, *, paths: dict[str, str]) -> str:
    """``text`` with times, PIDs, seconds left (also as JSON numbers), OS error texts and
    the given paths as placeholders."""
    for path, placeholder in sorted(paths.items(), key=lambda item: -len(item[0])):
        # JSON and OSError repr double Windows backslashes. Normalize the separator
        # after the prefix too: the goldens record filenames as <LOCK_DIR>/stop.json.
        variants = {path, json.dumps(path, ensure_ascii=False)[1:-1]}
        for variant in sorted(variants, key=len, reverse=True):
            for separator in ("\\\\", "\\", "/"):
                text = text.replace(variant + separator, placeholder + "/")
            text = text.replace(variant, placeholder)
    text = _TIME.sub("<TIME>", text)
    text = _PID.sub("PID <PID>", text)
    text = _JSON_NUMBERS.sub(r'"\1": "<NUMBER>"', text)
    text = _PAUSE_LEFT.sub("trwa jeszcze ok. <N> s", text)
    text = _OS_ERROR.sub("[Errno <N>] <OS error>", text)
    return _SECONDS_LEFT.sub("(za <N> s)", text)


def requests_sent(router: respx.MockRouter) -> list[str]:
    """Every request the mocked service got, in order: ``GET <url> [rsc: 1] [accept: …]``."""
    sent: list[str] = []
    for call in router.calls:
        request = call.request
        line = f"{request.method} {request.url}"
        for header in ("rsc", "accept"):
            if header in request.headers:
                line += f" [{header}: {request.headers[header]}]"
        sent.append(line)
    return sent


def check(surface: str, case: str, observed: dict[str, Any]) -> None:
    """``observed`` must equal ``tests/golden/<surface>/<case>.json``, byte for byte.

    With ``DEWELOPERUCH_UPDATE_GOLDEN=1`` the file is written first (the case passes).
    """
    path = GOLDEN / surface / f"{case}.json"
    text = json.dumps(observed, ensure_ascii=False, indent=2) + "\n"
    if os.environ.get(UPDATE_GOLDEN) == "1":
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    assert path.exists(), f"brak pliku {path}; nagraj go z {UPDATE_GOLDEN}=1"
    recorded = path.read_text(encoding="utf-8")
    # The parsed values first, for a readable diff; then the text (int vs float, order).
    assert json.loads(text) == json.loads(recorded)
    assert text == recorded


def recorded_cases(surface: str) -> set[str]:
    return {path.stem for path in (GOLDEN / surface).glob("*.json")}
