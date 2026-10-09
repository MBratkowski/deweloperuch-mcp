"""The service's base URL and the User-Agent have exactly one definition (D9)."""

import ast
import re
from pathlib import Path

import pytest

from deweloperuch_mcp import identity

REPO = Path(__file__).resolve().parent.parent

# TODO(U1): the user chooses the final User-Agent (D9). Changing it must be a
# deliberate decision, so the current value is pinned here, and only here.
EXPECTED_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)


def test_user_agent_is_pinned() -> None:
    assert identity.USER_AGENT == EXPECTED_USER_AGENT


def test_base_url_is_the_service_origin() -> None:
    # No trailing slash: callers append paths that start with "/".
    assert identity.BASE_URL == "https://deweloperuch.pl"


# --- one definition ------------------------------------------------------------

UA_VARIABLE = re.compile(r"(?i)^(ua|user_agent)$|_user_agent$")


def _literal_text(node: ast.AST) -> str | None:
    """Text of a str or bytes literal (adjacent literals are already one node)."""
    if isinstance(node, ast.Constant):
        if isinstance(node.value, str):
            return node.value
        if isinstance(node.value, bytes):
            return node.value.decode("utf-8", "replace")
    return None


def _is_header_name(name: str | None) -> bool:
    # "User-Agent", "user_agent", "USER-AGENT", ...
    return name is not None and name.lower().replace("_", "-") == "user-agent"


def _is_shared_constant(node: ast.expr) -> bool:
    # USER_AGENT, identity.USER_AGENT, config.USER_AGENT
    return (isinstance(node, ast.Name) and node.id == "USER_AGENT") or (
        isinstance(node, ast.Attribute) and node.attr == "USER_AGENT"
    )


def _is_ua_variable(target: ast.expr) -> bool:
    name = target.id if isinstance(target, ast.Name) else getattr(target, "attr", "")
    return bool(UA_VARIABLE.search(name))


def _contains_literal(node: ast.expr) -> bool:
    # Also inside f-strings and "a" + "b".
    return any(_literal_text(child) is not None for child in ast.walk(node))


def _defines_user_agent(node: ast.expr | ast.stmt | ast.keyword) -> bool:
    text = _literal_text(node)
    if text is not None:
        # The value itself (also once U1 replaces it) and any browser-style User-Agent.
        return identity.USER_AGENT in text or "Mozilla/" in text
    if isinstance(node, ast.Dict):  # headers={"User-Agent": ...}
        return any(
            key is not None
            and _is_header_name(_literal_text(key))
            and not _is_shared_constant(value)
            for key, value in zip(node.keys, node.values, strict=True)
        )
    if isinstance(node, ast.keyword):  # user_agent=...
        return _is_header_name(node.arg) and not _is_shared_constant(node.value)
    if isinstance(node, ast.Assign | ast.AnnAssign):  # ua = "...", self._user_agent = f"..."
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        return (
            node.value is not None
            and any(_is_ua_variable(target) for target in targets)
            and _contains_literal(node.value)
        )
    return False


def user_agent_definitions(source: str) -> list[int]:
    """Lines where ``source`` defines a User-Agent of its own instead of using USER_AGENT.

    Static backstop only. Not covered: ``headers["User-Agent"] = "x"`` (Subscript
    target), ``req.add_header("User-Agent", "x")``, ``[("User-Agent", "x")]`` and
    ``h.setdefault("user-agent", "x")``, unless the value contains "Mozilla/" or the
    current USER_AGENT. The HTTP client therefore needs a behaviour test (respx)
    asserting every request sends ``identity.USER_AGENT``.
    """
    return sorted(
        {
            node.lineno
            for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.expr | ast.stmt | ast.keyword) and _defines_user_agent(node)
        }
    )


@pytest.mark.parametrize(
    "source",
    [
        'UA = "Mozilla/5.0 (X11; Linux x86_64)"',
        'def send():\n    """Looks like Mozilla/5.0 to the server."""',
        'HEADER = b"User-Agent: Mozilla/5.0"',
        'headers = {"User-Agent": "deweloperuch-mcp/0.1"}',
        'headers = {"user_agent": ua}',
        'headers = {b"USER-AGENT": config.UA}',
        'client = Client(user_agent="deweloperuch-mcp/0.1")',
        "headers = dict(User_Agent=USER_AGENT_V2)",
        'ua = "deweloperuch-mcp/0.1"',
        'DEFAULT_USER_AGENT: str = "deweloperuch-mcp/0.1"',
        'self._user_agent = f"deweloperuch-mcp/{VERSION}"',
        'user_agent = "deweloperuch-mcp/" + VERSION',
    ],
)
def test_guard_flags_own_user_agent(source: str) -> None:
    assert user_agent_definitions(source) != []


@pytest.mark.parametrize(
    "source",
    [
        "from deweloperuch_mcp.identity import USER_AGENT",
        'headers = {"User-Agent": USER_AGENT}',
        'headers = {"User-Agent": identity.USER_AGENT, "RSC": "1"}',
        'client = Client(headers={"user-agent": config.USER_AGENT})',
        'kwargs = {**defaults, "Accept": "text/x-component"}',
        "ua = USER_AGENT",
        "self._user_agent = user_agent",
        'HEADER_NAME = "User-Agent"',
        'message = "User-Agent is fixed by D9"',
        '__all__ = ["BASE_URL", "USER_AGENT"]',
        'payload = b"\\xff\\xfe"',
    ],
)
def test_guard_accepts_shared_constant_and_header_name(source: str) -> None:
    assert user_agent_definitions(source) == []


def test_guard_finds_a_copy_of_any_value(monkeypatch: pytest.MonkeyPatch) -> None:
    """Once U1 picks a non-browser value, a pasted copy is still caught."""
    value = "deweloperuch-mcp/1.0 (+kontakt)"
    monkeypatch.setattr(identity, "USER_AGENT", value)

    source = f'import x\n\nHEADERS = [("Accept", "*/*"), ("X-Client", "{value}")]'

    assert user_agent_definitions(source) == [3]


def test_user_agent_is_defined_only_in_identity() -> None:
    """No other code in src/ or recon/ carries its own User-Agent."""
    found = {
        path.relative_to(REPO): lines
        for top in ("src", "recon")
        for path in sorted((REPO / top).rglob("*.py"))
        if (lines := user_agent_definitions(path.read_text(encoding="utf-8")))
    }

    expected = {Path("src/deweloperuch_mcp/identity.py")}
    # A#3 switches the scanner to config.USER_AGENT. The exception expires on its own
    # once the old literal is gone: if the scanner is still flagged then (e.g. via an
    # alias such as `USER_AGENT as UA`), this test fails and the guard must learn it.
    if "Mozilla/" in (REPO / "recon/scan_bundles.py").read_text(encoding="utf-8"):
        expected.add(Path("recon/scan_bundles.py"))
    assert set(found) == expected, (
        f"User-Agent definitions (file: lines): {found}. The value must be one literal "
        "(adjacent strings are fine) assigned to USER_AGENT in identity.py and nowhere "
        "else; elsewhere use identity.USER_AGENT (config.USER_AGENT in recon/). A docstring "
        "that mentions 'Mozilla/' or a value built with '+' or an f-string counts as a "
        "definition too."
    )
