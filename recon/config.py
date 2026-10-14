"""Shared configuration for recon scripts (stdlib only).

Recon scripts run as ``python3 recon/<script>.py`` without installing the package.
Importing this module puts the repo's ``src/`` first on ``sys.path`` and re-exports
what the package's HTTP client uses too, so recon and the client share it:

- ``BASE_URL`` and ``USER_AGENT``, defined once in ``deweloperuch_mcp.identity`` (D9);
- ``parse_retry_after`` (``deweloperuch_mcp.retry_after``), the one ``Retry-After`` parser;
- the response policy (``deweloperuch_mcp.http_policy``): what stops a series of
  requests, how long the limiter pauses, the body size limit;
- the RSC ("flight") request token and decoder (``deweloperuch_mcp.flight``), which
  ``recon/flight.py`` re-exports;
- the read allowlist (``deweloperuch_mcp.allowlist``), which ``recon/allowlist.py``
  re-exports;
- the single limiter implementation (``deweloperuch_mcp.throttle``), so they share
  one lock and one STOP record (``StoppedError``)::

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

# These imports need the sys.path entry above. BASE_URL and USER_AGENT are
# defined only in deweloperuch_mcp.identity; do not redefine them here.
from deweloperuch_mcp.allowlist import (  # noqa: E402
    API_PATHS,
    DUMP_PATHS,
    EXCLUDED_API_PATHS,
    PAGE_ROUTES,
    compile_template,
    match_api,
    match_dump,
    match_excluded_api,
    match_page,
)
from deweloperuch_mcp.flight import (  # noqa: E402
    component_props,
    find_json_after,
    flight,
    flight_from_html,
    rsc_token,
    with_rsc_token,
)
from deweloperuch_mcp.http_policy import (  # noqa: E402
    MAX_BODY_BYTES,
    PAUSE_AFTER_5XX,
    PAUSE_AFTER_429,
    body_length,
    content_type,
    is_html,
    pause_seconds,
    stop_cause,
    stop_reason,
)
from deweloperuch_mcp.identity import BASE_URL, USER_AGENT  # noqa: E402
from deweloperuch_mcp.retry_after import parse_retry_after  # noqa: E402
from deweloperuch_mcp.throttle import (  # noqa: E402
    DEFAULT_MAX_WAIT,
    DEFAULT_MIN_INTERVAL,
    RequestLimiter,
    Slot,
    StoppedError,
    StopRecord,
    WaitTooLongError,
    default_lock_dir,
    format_time,
)

__all__ = [
    "API_PATHS",
    "BASE_URL",
    "DUMP_PATHS",
    "EXCLUDED_API_PATHS",
    "PAGE_ROUTES",
    "DEFAULT_MAX_WAIT",
    "DEFAULT_MIN_INTERVAL",
    "MAX_BODY_BYTES",
    "PAUSE_AFTER_429",
    "PAUSE_AFTER_5XX",
    "USER_AGENT",
    "RequestLimiter",
    "Slot",
    "StopRecord",
    "StoppedError",
    "WaitTooLongError",
    "body_length",
    "compile_template",
    "component_props",
    "content_type",
    "default_lock_dir",
    "find_json_after",
    "flight",
    "flight_from_html",
    "format_time",
    "is_html",
    "match_api",
    "match_dump",
    "match_excluded_api",
    "match_page",
    "parse_retry_after",
    "pause_seconds",
    "rsc_token",
    "stop_cause",
    "stop_reason",
    "with_rsc_token",
]
