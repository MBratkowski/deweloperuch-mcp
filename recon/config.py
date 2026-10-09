"""Shared configuration for recon scripts (stdlib only).

Recon scripts run as ``python3 recon/<script>.py`` without installing the package.
Importing this module puts the repo's ``src/`` first on ``sys.path`` and re-exports
what the package's HTTP client uses too, so recon and the client share it:

- ``BASE_URL`` and ``USER_AGENT``, defined once in ``deweloperuch_mcp.identity`` (D9);
- ``parse_retry_after`` (``deweloperuch_mcp.retry_after``), the one ``Retry-After`` parser;
- the single limiter implementation (``deweloperuch_mcp.throttle``), so they share
  one lock::

    from config import BASE_URL, USER_AGENT, RequestLimiter

    limiter = RequestLimiter()
    with limiter.slot() as slot:
        ...

Keep this file parseable by old Pythons (e.g. the macOS system python3 3.9): the
version check below must run and explain the problem before anything else fails.
"""

import sys
from pathlib import Path

# recon runs on whatever python3 is on PATH, not on the project's interpreter.
if sys.version_info < (3, 11):  # noqa: UP036
    sys.exit(
        "recon/ wymaga Pythona 3.11 lub nowszego, uruchomiono "
        f"{sys.version_info[0]}.{sys.version_info[1]}. Użyj nowszego python3 "
        "albo `uv run python recon/<skrypt>.py`."
    )

_SRC = str(Path(__file__).resolve().parent.parent / "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

# These imports need the sys.path entry above. BASE_URL and USER_AGENT (TODO(U1)) are
# defined only in deweloperuch_mcp.identity; do not redefine them here.
from deweloperuch_mcp.identity import BASE_URL, USER_AGENT  # noqa: E402
from deweloperuch_mcp.retry_after import parse_retry_after  # noqa: E402
from deweloperuch_mcp.throttle import (  # noqa: E402
    DEFAULT_MAX_WAIT,
    DEFAULT_MIN_INTERVAL,
    RequestLimiter,
    Slot,
    WaitTooLongError,
    default_lock_dir,
)

__all__ = [
    "BASE_URL",
    "DEFAULT_MAX_WAIT",
    "DEFAULT_MIN_INTERVAL",
    "USER_AGENT",
    "RequestLimiter",
    "Slot",
    "WaitTooLongError",
    "default_lock_dir",
    "parse_retry_after",
]
