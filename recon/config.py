"""Shared configuration for recon scripts (stdlib only).

Recon scripts run as ``python3 recon/<script>.py`` without installing the package.
Importing this module puts the repo's ``src/`` first on ``sys.path`` and re-exports
the single limiter implementation (``deweloperuch_mcp.throttle``), which the
package's HTTP client uses too, so recon and the client share one lock::

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

from deweloperuch_mcp.throttle import (  # noqa: E402 - needs the sys.path entry above
    DEFAULT_MIN_INTERVAL,
    RequestLimiter,
    Slot,
    WaitTooLongError,
    default_lock_dir,
)

BASE_URL = "https://deweloperuch.pl"

# TODO(U1): the user picks the final User-Agent when deciding U1 (D9). Until then this
# is the value recon/scan_bundles.py has been sending (that script switches to this
# constant in A#3). Do not define a User-Agent anywhere else.
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)

__all__ = [
    "BASE_URL",
    "DEFAULT_MIN_INTERVAL",
    "USER_AGENT",
    "RequestLimiter",
    "Slot",
    "WaitTooLongError",
    "default_lock_dir",
]
