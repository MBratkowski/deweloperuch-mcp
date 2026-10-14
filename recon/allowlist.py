"""Read channels recon/probe.py may call (stdlib only).

The allowlist lives in the package (``deweloperuch_mcp.allowlist``), so probe and the
package's HTTP transport check paths against one list; this module re-exports it
through config. Every entry comes from the discovery docs; change the docs first
(recon-verifier), then the package module. tests/recon_scripts/test_probe_allowlist.py keeps both in
sync.

Keep this file parseable by Python 3.9: Python compiles the whole file before config's
version check runs.
"""

# config goes first: it stops Python < 3.11 with a clear message and puts src/ on
# sys.path, where the allowlist lives.
import config  # noqa: F401

# isort: split
from config import (
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

__all__ = [
    "API_PATHS",
    "DUMP_PATHS",
    "EXCLUDED_API_PATHS",
    "PAGE_ROUTES",
    "compile_template",
    "match_api",
    "match_dump",
    "match_excluded_api",
    "match_page",
]
