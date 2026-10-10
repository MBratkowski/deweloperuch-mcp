"""How this project addresses and identifies itself to deweloperuch.pl.

The one definition of the service origin and of the User-Agent sent with every
request (D9). It lives in the package, not in ``recon/``, because an installed
package (e.g. via ``uvx``) does not see the repo's ``recon/`` directory; recon
scripts get these constants through ``recon/config.py``, which re-exports them.

Keep this module free of imports: ``recon/`` scripts load it without installing
the package or its dependencies.
"""

BASE_URL = "https://deweloperuch.pl"
"""Service origin, without a trailing slash."""

# TODO(U1): the user picks the final User-Agent when deciding U1 (D9). Until then this
# is the value recon/scan_bundles.py had been sending on its own before A#3; now every
# request (probe, scanner, the package's client) sends this constant. Do not define a
# User-Agent anywhere else; tests/test_identity.py guards that.
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
)
