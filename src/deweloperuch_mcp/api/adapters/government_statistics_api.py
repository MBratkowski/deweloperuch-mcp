"""``GovernmentStatisticsApi``: the government statistics (GUS, NBP, Eurostat) of a
location, the ``GovernmentStatisticsSource`` port: the page
``/statystyki/{location}/dane-rzadowe`` (RSC, D1) [P 2026-10-31], read into
``GovernmentStatsPageDto``.

The page is an internal channel of the site's UI, not an API: it may change at any deploy
without notice (D21). Its 1.0 route ``/statystyki/statystyki-rzadowe/{location}`` answers
308 to it [P 2026-10-29], which the transport reads as a changed service.
"""

from functools import partial

from deweloperuch_mcp.api.dto.government_stats_page_dto import GovernmentStatsPageDto
from deweloperuch_mcp.api.http.rsc_page import RscPage
from deweloperuch_mcp.api.http.transport import HttpClient
from deweloperuch_mcp.models.errors import SERVICE_CHANGED, NotFoundError, UnexpectedResponseError
from deweloperuch_mcp.models.government_statistics import Dataset, LocationStatistics
from deweloperuch_mcp.models.values import LocationSlug

KNOWN_LOCATIONS = frozenset(
    {
        "polska",
        "7-miast",
        "10-miast",
        "6-miast-bez-warszawy",
        "biala-podlaska",
        "bialystok",
        "bielsko-biala",
        "bydgoszcz",
        "bytom",
        "chelm",
        "chorzow",
        "czestochowa",
        "dabrowa-gornicza",
        "elblag",
        "gdansk",
        "gdynia",
        "gliwice",
        "gorzow-wielkopolski",
        "grudziadz",
        "jastrzebie-zdroj",
        "jaworzno",
        "jelenia-gora",
        "kalisz",
        "katowice",
        "kielce",
        "konin",
        "koszalin",
        "krakow",
        "krosno",
        "legnica",
        "leszno",
        "lodz",
        "lomza",
        "lublin",
        "myslowice",
        "nowy-sacz",
        "olsztyn",
        "opole",
        "ostroleka",
        "piekary-slaskie",
        "piotrkow-trybunalski",
        "plock",
        "poznan",
        "przemysl",
        "radom",
        "ruda-slaska",
        "rybnik",
        "rzeszow",
        "siedlce",
        "siemianowice-slaskie",
        "skierniewice",
        "slupsk",
        "sopot",
        "sosnowiec",
        "suwalki",
        "swietochlowice",
        "swinoujscie",
        "szczecin",
        "tarnobrzeg",
        "tarnow",
        "torun",
        "tychy",
        "walbrzych",
        "warszawa",
        "wloclawek",
        "wroclaw",
        "zabrze",
        "zamosc",
        "zielona-gora",
        "zory",
    }
)
"""``polska`` and the 69 locations its page links as „Dostępne lokalizacje danych
rządowych”: 3 aggregates and 66 cities [P 2026-10-31, tests/fixtures/rsc/
stats_gov_polska_20261031.rsc; the pages of ``warszawa`` and ``7-miast`` link the same but
themselves].
The section is one catch-all route (pages-rsc.md), so a renamed or removed page would
answer each of them like an unknown location: for these, "unknown" is a change of the
service (D21), never a wrong argument."""

_MOVED = (
    "Narzędzie nie może pobrać tych danych, bo serwis przeniósł je w inne miejsce albo "
    "przestał je udostępniać. To nie musi znaczyć, że argumenty są błędne ani że szukanego "
    f"obiektu nie ma. {SERVICE_CHANGED}"
)
"""The transport's message for a moved or removed route (D21), word for word: a model
reads every change of the service alike (the transport has no constant of it)."""


class GovernmentStatisticsApi:
    """``usecases.ports.GovernmentStatisticsSource`` of the service: one page request per
    location (the transport's cache answers the next datasets of the same location);
    ``statistics_page`` is its resource as the service sends it (DTO)."""

    def __init__(self, http: HttpClient) -> None:
        self._http = http

    def location_statistics(self, location: LocationSlug, dataset: Dataset) -> LocationStatistics:
        page = self.statistics_page(location)
        return page.to_model(location, dataset, path=self.path(location.value))

    def statistics_page(self, location: LocationSlug) -> GovernmentStatsPageDto:
        """The sections, the location and every data prop the page has
        (``GovernmentStatsPageDto.from_payload``, with its errors).

        An unknown location is a 404 whose body is a flight stream (``text/x-component``)
        [P 2026-10-31, docs/discovery/endpoints.md section 9, "Pages"], a ``NotFoundError``
        of the transport (or of the DTO, for Next.js's marker in a 200), except for
        ``KNOWN_LOCATIONS``: for them it is a changed service (``UnexpectedResponseError``).
        """
        path = self.path(location.value)
        decode = partial(GovernmentStatsPageDto.from_payload, path=path, location=location)
        try:
            return self._page(path).read(decode)
        except NotFoundError as err:
            if location.value not in KNOWN_LOCATIONS:
                raise
            raise UnexpectedResponseError(
                _MOVED, detail=f"{err.detail or path} (lokalizacja serwisu {location.value!r})"
            ) from err

    def _page(self, path: str) -> RscPage:
        """The one place the page is read: its 404 ``text/x-component`` is the page's own
        answer to an unknown location [P 2026-10-31, 2 of 2 statistics pages]."""
        return RscPage(self._http, path, unknown_404=True)

    @staticmethod
    def path(location: str) -> str:
        """``/statystyki/{location}/dane-rzadowe`` [P 2026-10-31]: ``polska``, an aggregate or
        a city slug (the page of ``polska`` lists 3 aggregates and 66 cities)."""
        return f"/statystyki/{HttpClient.segment(location)}/dane-rzadowe"
