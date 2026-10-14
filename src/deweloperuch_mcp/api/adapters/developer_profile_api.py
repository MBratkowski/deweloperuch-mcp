"""``DeveloperProfileApi``: a developer's profile on the service, the ``DeveloperDirectory``
port.

- the profile in a city or the whole country: the object prop ``data`` of
  ``/ceny-ofertowe/{city}/deweloperzy/{developerSlug}`` (RSC) [P]; an unknown developer is
  a page with a heading instead (``DEVELOPER_NOT_FOUND``).
"""

from deweloperuch_mcp.api.dto.developer_page_dto import DeveloperPageDto
from deweloperuch_mcp.api.http.rsc_page import RscPage
from deweloperuch_mcp.api.http.transport import HttpClient
from deweloperuch_mcp.models.developer_profile import DeveloperProfile
from deweloperuch_mcp.models.values import CitySlug, DeveloperSlug

DEVELOPER_NOT_FOUND = "Deweloper nie znaleziony"
"""The heading of the page of a developer the service does not know.

[P 2026-10-13] tests/fixtures/rsc/developer_unknown_warszawa.rsc: HTTP 200 without the
``data`` prop and without Next.js's 404 marker, an ``h1`` with this text instead.
"""


class DeveloperProfileApi:
    """``usecases.ports.DeveloperDirectory`` of the service; ``developer_page`` is its
    resource as the service sends it (DTO)."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def developer(self, slug: DeveloperSlug, city: CitySlug) -> DeveloperProfile:
        return self.developer_page(city.value, slug.value).to_model(city)

    def developer_page(self, city: str, developer_slug: str) -> DeveloperPageDto:
        """The object prop ``data`` of the developer's profile in ``city`` [P].

        ``NotFoundError`` for the page of an unknown developer (``DEVELOPER_NOT_FOUND``)
        and for Next.js's 404 marker (an unknown city may answer so, [H]).
        """
        page = RscPage(self._http, self.path(city, developer_slug))
        return page.prop("data", DeveloperPageDto, missing=DEVELOPER_NOT_FOUND)

    @staticmethod
    def path(city: str, developer_slug: str) -> str:
        """``/ceny-ofertowe/{city}/deweloperzy/{developerSlug}`` [P]: ``city`` is a city slug
        or ``polska``. Also the path of the link to the profile (``links``, D12)."""
        city, developer = HttpClient.segment(city), HttpClient.segment(developer_slug)
        return f"/ceny-ofertowe/{city}/deweloperzy/{developer}"
