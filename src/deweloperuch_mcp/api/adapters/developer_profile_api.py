"""``DeveloperProfileApi``: a developer's profile on the service, the ``DeveloperDirectory``
port.

- the profile in a city or the whole country: the page
  ``/ceny-ofertowe/{city}/deweloperzy/{developerSlug}`` (RSC), read in one request by
  ``DeveloperPageDto.from_payload`` (the ``hero`` element's props and the chart of
  cities) [P 2026-10-31]. D21: the page is an internal channel of the site's UI and may
  change without notice; a page without its props, a redirect, a 410 or an HTML 404 is a
  changed service, never an unknown developer;
- an unknown developer is a 200 with Next.js's 404 marker, in a city and in the whole
  country [P 2026-10-31] (tests/fixtures/rsc/developer_unknown_*_20261031.rsc; 1.0 showed
  a heading instead);
- a known developer in a city the service does not know is a 200 whose error row redirects
  to the developer's page for the whole country [P 2026-11-02] (T39,
  tests/fixtures/rsc/developer_unknown_city_20261102.rsc): not found as well, by D21
  (exception for T39); any other redirect is a changed service.
"""

from functools import partial

from deweloperuch_mcp.api.dto.developer_page_dto import DeveloperPageDto
from deweloperuch_mcp.api.http.rsc_page import RscPage
from deweloperuch_mcp.api.http.transport import HttpClient
from deweloperuch_mcp.models.developer_profile import DeveloperProfile
from deweloperuch_mcp.models.values import WHOLE_COUNTRY, CitySlug, DeveloperSlug


class DeveloperProfileApi:
    """``usecases.ports.DeveloperDirectory`` of the service; ``developer_page`` is its
    resource as the service sends it (DTO)."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def developer(self, slug: DeveloperSlug, city: CitySlug) -> DeveloperProfile:
        return self.developer_page(city.value, slug.value).to_model(city)

    def developer_page(self, city: str, developer_slug: str) -> DeveloperPageDto:
        """The developer, its investments in ``city`` and its cities, from one page
        (``DeveloperPageDto.from_payload``, with its errors; a city's page may send the reader
        on to the developer's page for the whole country)."""
        path = self.path(city, developer_slug)
        country = self.path(WHOLE_COUNTRY, developer_slug)
        decode = partial(
            DeveloperPageDto.from_payload, path=path, country=None if path == country else country
        )
        return RscPage(self._http, path).read(decode)

    @staticmethod
    def path(city: str, developer_slug: str) -> str:
        """``/ceny-ofertowe/{city}/deweloperzy/{developerSlug}`` [P; 200 on 2.0 for a city and
        for ``polska``, 2026-10-31]: ``city`` is a city slug or ``polska``. Also the path of
        the link to the profile (``links``, D12)."""
        city, developer = HttpClient.segment(city), HttpClient.segment(developer_slug)
        return f"/ceny-ofertowe/{city}/deweloperzy/{developer}"
