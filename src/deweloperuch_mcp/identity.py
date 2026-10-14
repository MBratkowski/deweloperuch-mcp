"""How this project addresses and identifies itself to deweloperuch.pl.

The one definition of the service origin and of the User-Agent sent with every
request (D9). It lives in the package, not in ``recon/``, because an installed
package (e.g. via ``uvx``) does not see the repo's ``recon/`` directory; recon
scripts get these constants through ``recon/config.py``, which re-exports them.

Keep this module stdlib-only: ``recon/`` scripts load it without installing the
package or its dependencies.
"""

from importlib import metadata

BASE_URL = "https://deweloperuch.pl"
"""Service origin, without a trailing slash."""

DISTRIBUTION = "deweloperuch-mcp"
"""The package's name, also the product name in the User-Agent."""

REPOSITORY_URL = "https://github.com/MBratkowski/deweloperuch-mcp"

UNKNOWN_VERSION = "0+unknown"
"""The version when no package metadata is available (e.g. ``python3 recon/<script>.py``)."""


def installed_version() -> str:
    """The installed package's version, or ``UNKNOWN_VERSION`` without package metadata."""
    try:
        return metadata.version(DISTRIBUTION)
    except metadata.PackageNotFoundError:
        return UNKNOWN_VERSION


# The authors of deweloperuch.pl agreed to this project's use of the service on
# 2026-10-14. The client says what it is: the project's name and version, and its
# repository as the contact, in the usual "product/version (+URL)" form (D2). Do not
# define a User-Agent anywhere else; tests/architecture/test_identity.py guards that.
USER_AGENT = f"{DISTRIBUTION}/{installed_version()} (+{REPOSITORY_URL})"
