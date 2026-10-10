"""The Bash safety-net hook blocks ad-hoc live calls to the service (CLAUDE.md, D10) and
lifting a STOP, which only the user may do.

The hook runs in its own process exactly as Claude Code starts it (``python3
<hook>`` with the tool call as JSON on stdin); exit code 2 blocks the command,
0 lets it through. Nothing here touches the network: the hook only reads text.
"""

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
HOOK = REPO / ".claude" / "hooks" / "guard_live_calls.py"

# Assembled in code, so the templates below read as commands without the repo
# carrying ready-to-paste service addresses.
HOST = "deweloperuch" + ".pl"

BLOCKED = 2
ALLOWED = 0

# Host without a scheme plus a network tool. Unambiguous names (curl, wget, ...)
# count anywhere in the command, so wrappers, loops and quoted code are caught.
TOOL_WITH_HOST = [
    "curl -s <host>/api/x",
    "curl -s www.<host>/api/x",
    "for p in a b; do curl -s <host>/api/$p; done",
    "for p in a b\ndo curl -s <host>/api/$p\ndone",
    "if curl -sf <host>/api/x; then echo ok; fi",
    "while ! curl -sf <host>/api/x; do sleep 1; done",
    "timeout 10 curl -s <host>/api/x",
    "timeout 10s wget -qO- <host>/api/x",
    "bash -c 'curl -s <host>/api/x'",
    'sh -c "wget -qO- <host>/api/x"',
    "eval curl <host>/api/x",
    "{ curl -s <host>/api/x; }",
    "! curl -s <host>/api/x",
    "python3 -c \"import os; os.system('curl <host>/api/x')\"",
    "python3 -c \"import subprocess; subprocess.run(['curl', '<host>/api/x'])\"",
    "watch -n 5 curl -s <host>/api/x",
    "nice -n 10 curl <host>/api/x",
    "parallel curl ::: <host>/api/a <host>/api/b",
    "sudo -u x curl <host>/api/x",
    "\\curl <host>/api/x",
    "echo 'curl <host>/api/x' | sh",
    "X=$(curl -s <host>/api/x)",
    "echo `curl <host>/api/x`",
    "cd /tmp && wget <host>/api/x",
    "cd /tmp &&curl <host>/api/x",
    "cat body.json |\tcurl -d @- <host>/api/x",
    "FOO=1 /usr/bin/curl <host>/api/x",
    "env -i PATH=/usr/bin curl <host>/api/x",
    "CURL <host>/x",
    # Names that are also common words (http, nc, openssl, ...) count only in
    # command position.
    "http GET <host>/api/x",
    "cd /tmp && /opt/bin/https <host>/api/x",
    "nc <host> 443",
    "openssl s_client -connect <host>:443",
    "exec 3<>/dev/tcp/<host>/443",
]

# Known and accepted false alarms (not asserted): curl/wget as plain text next to the
# host also blocks, e.g. grep -E 'curl|wget' f | grep <host>, rg '(curl|wget).*<host>',
# echo 'curl is installed' && grep <host>, a heredoc mentioning curl and the host.
# Narrowing that further is a deliberate hook change, not a test tweak.

# A full service URL blocks whatever the command is.
SERVICE_URL = [
    "python3 recon/probe.py https://<host>/api/cities",
    "echo https://<host>/",
    "open http://www.<host>/",
    # Known and accepted false alarm: prose counts too, e.g. a commit message.
    # Write the host without a scheme there.
    'git commit -m "Link https://<host>/ in README"',
]

PASSES = [
    # Probe and scanner take paths, never URLs.
    'python3 recon/probe.py api "/api/cities?q=krak"',
    "python3 recon/scan_bundles.py --json",
    # The host alone, or "http" outside command position, is just text.
    'grep -rn "<host>" docs/',
    "git log --oneline -- docs | grep -i <host>",
    "sed -n '1,5p' docs/http/<host>.md",
    "gh api users/deweloperuch/repos",
    "python3 -c \"print('HTTP client for <host>')\"",
    'git commit -m "Fix HTTP retry for <host> limiter"',
    "sed -i '' 's/http status of <host>/x/' notes.md",
    # A network tool without the service host.
    "curl https://api.github.com/",
]


def run_hook(stdin: str) -> int:
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input=stdin,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    return result.returncode


def run_hook_on(template: str) -> int:
    command = template.replace("<host>", HOST)
    return run_hook(json.dumps({"tool_input": {"command": command}}))


@pytest.mark.parametrize("template", TOOL_WITH_HOST)
def test_blocks_network_tool_with_service_host(template: str) -> None:
    assert run_hook_on(template) == BLOCKED


@pytest.mark.parametrize("template", SERVICE_URL)
def test_blocks_any_command_with_service_url(template: str) -> None:
    assert run_hook_on(template) == BLOCKED


@pytest.mark.parametrize("template", PASSES)
def test_lets_other_commands_through(template: str) -> None:
    assert run_hook_on(template) == ALLOWED


@pytest.mark.parametrize("stdin", ["not json", "", '{"tool_input": '])
def test_blocks_when_input_is_malformed(stdin: str) -> None:
    """Fail-closed: a hook that cannot read the command must not wave it through."""
    assert run_hook(stdin) == BLOCKED


# --- lifting a STOP is for the user only (CLAUDE.md) ---------------------------------------

# Assembled in code, so that running or editing this file is not itself blocked.
CLI = "deweloperuch"
CLEAR = "stop " + "clear"
RECORD = "stop" + ".json"
LOCK = "throttle" + ".lock"
LIMITER_DIR = "~/.cache/" + "deweloperuch-mcp"
CACHE = LIMITER_DIR + "/"

LIFTS_STOP = [
    # The CLI command in any form, also behind a wrapper or after another command.
    f"{CLI} {CLEAR}",
    f"uv run {CLI} {CLEAR}",
    f".venv/bin/{CLI} {CLEAR}",
    f"/Users/x/deweloperuch-mcp/.venv/bin/{CLI} {CLEAR}",
    f"python -m deweloperuch_mcp.cli {CLEAR}",
    f"XDG_CACHE_HOME=/tmp/x uv run {CLI} {CLEAR}",
    f"cd /tmp && {CLI} {CLEAR}",
    f"{CLI} stop status; {CLI} {CLEAR}",
    f"{CLI} stop status && uv run {CLI} {CLEAR}",
    f"bash -c '{CLI} {CLEAR}'",
    f"{CLI}   stop\tclear",
    # The record itself: removed, moved, emptied, overwritten, edited.
    f"rm {CACHE}{RECORD}",
    f'rm -f "$XDG_CACHE_HOME/deweloperuch-mcp/{RECORD}"',
    f"mv {CACHE}{RECORD} /tmp/",
    f"unlink {CACHE}{RECORD}",
    f"echo '{{}}' > {CACHE}{RECORD}",
    f": >{CACHE}{RECORD}",
    f"truncate -s0 {CACHE}{RECORD}",
    f"sed -i '' 's/403/200/' {CACHE}{RECORD}",
    f"python3 -c \"import os; os.remove('{CACHE}{RECORD}')\"",
    f"python3 -c \"import pathlib; pathlib.Path('{RECORD}').unlink()\"",
    f"python3 -c \"open('{RECORD}', 'w').write('x')\"",
    f"find ~/.cache -name {RECORD} -exec rm {{}} +",
    # The command split by a line continuation, quoted word by word, or with a comment
    # that only mentions --help.
    f"uv run {CLI} \\\n{CLEAR}",
    f"uv run {CLI} stop \\\nclear",
    f"uv run {CLI} stop 'clear'",
    f'uv run {CLI} "stop" "clear"',
    f"uv run {CLI} {CLEAR}  # not --help",
    # The limiter's directory (the record and the 429 pause) and the lock file.
    f"rm -rf {LIMITER_DIR}",
    f"rm -rf {LIMITER_DIR}/",
    'rm -rf "$XDG_CACHE_HOME/deweloperuch-mcp"',
    "rm -rf ${XDG_CACHE_HOME}/deweloperuch-mcp/*",
    f"mv {LIMITER_DIR} /tmp/old",
    f"rm {LIMITER_DIR}/stop.*",
    f"find {LIMITER_DIR} -name 'stop*' -delete",
    f"rm {LIMITER_DIR}/{LOCK}",
    f": > {LIMITER_DIR}/{LOCK}",
    f"echo x >| {CACHE}{RECORD}",
    f"echo x >{RECORD}",
]

STOP_PASSES = [
    f"uv run {CLI} stop status",
    f"uv run {CLI} stop status --json",
    f"uv run {CLI} {CLEAR} --help",
    f"uv run {CLI} stop --help",
    f"cat {CACHE}{RECORD}",
    f"ls -la {CACHE} 2>&1",
    f"ls -la {CACHE}{RECORD} 2>/dev/null",
    f"grep -rn '{RECORD}' src tests | head",
    "grep -rn 'os.replace' src/deweloperuch_mcp/throttle.py",
    "uv run pytest -q",
    "git status --porcelain",
    # Other directories of the same name, reading the limiter's files, unrelated redirects.
    "rm -rf /Users/x/Projects/deweloperuch-mcp/build",
    "rm -rf .pytest_cache",
    f"ls -la {LIMITER_DIR}/",
    f"du -sh {LIMITER_DIR}",
    f"cat {LIMITER_DIR}/{LOCK}",
    "uv run pytest -q > /tmp/out.txt 2>&1",
    f"ls {CACHE}{RECORD} > /tmp/ls.txt",
]

# Known and accepted false alarms (not asserted): the CLI name next to the phrase as
# plain text also blocks, e.g. grep -rn "deweloperuch <phrase>" docs, an echo or a commit
# message quoting the command; so does the record's name, the lock's name or the limiter's
# directory next to a tool or call name used as text, e.g. rg 'rm .*<record>', grep -n
# 'open(' near <lock>, or cp of an unrelated file in a command that also lists the
# directory. Narrowing that is a deliberate hook change, not a test tweak.


@pytest.mark.parametrize("command", LIFTS_STOP)
def test_blocks_lifting_a_stop(command: str) -> None:
    assert run_hook_on(command) == BLOCKED


@pytest.mark.parametrize("command", STOP_PASSES)
def test_lets_reading_the_stop_through(command: str) -> None:
    assert run_hook_on(command) == ALLOWED


@pytest.mark.parametrize(
    "command",
    [
        ("a " * 50_000) + RECORD + (" b>" * 20_000),
        f"{CLI} " + "stop " * 30_000,
        ";".join([f"{CLI} stop status"] * 5_000),
        ">" * 100_000,
        "a>" * 50_000,
        RECORD + ">" * 100_000,
        RECORD + "a>" * 50_000,
        (RECORD + ".") * 10_000,
        "\\\n" * 50_000,
        "'" * 100_000,
    ],
    ids=[
        "record and redirects",
        "repeated stop",
        "many segments",
        "redirects",
        "short redirects",
        "record then redirects",
        "record then short redirects",
        "repeated record",
        "line continuations",
        "quotes",
    ],
)
def test_a_long_command_is_checked_fast(command: str) -> None:
    """No catastrophic backtracking: about 100 000 characters within a second, process
    start included."""
    assert len(command) >= 90_000
    start = time.perf_counter()
    run_hook_on(command)
    assert time.perf_counter() - start < 1.0
