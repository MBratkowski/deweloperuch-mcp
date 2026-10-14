"""The service's addresses as the tests use them: the base URL, the offers pages, the
page links."""

from deweloperuch_mcp import identity
from deweloperuch_mcp.api.links import ServicePageLinks

BASE = identity.BASE_URL

PAGES = BASE + "/ceny-ofertowe"
"""The offers pages of the service: the root of the page links (D12)."""

LINKS = ServicePageLinks()
"""The page links as the session builds them."""
