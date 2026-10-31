"""Tests of ``deweloperuch_mcp.api.links``."""

import urllib.parse

import pytest

from deweloperuch_mcp import identity
from deweloperuch_mcp.allowlist import match_dump, match_page
from deweloperuch_mcp.api.adapters.transaction_statistics_api import TransactionStatisticsApi
from deweloperuch_mcp.api.http.transport import HttpClient
from deweloperuch_mcp.api.links import ServicePageLinks
from deweloperuch_mcp.models.building import BuildingRef
from deweloperuch_mcp.models.transaction_series import TransactionCity
from deweloperuch_mcp.models.values import CitySlug
from deweloperuch_mcp.usecases.ports import RankingLinks
from deweloperuch_mcp.usecases.search_offers import SearchOffersRequest
from support.builders.developer_search import PROFILES
from support.providers.routes.buildings import BUILDING_PAGE, SLUG
from support.providers.samples import envelope, request_target
from support.providers.service import BASE


def path_of(url: str) -> str:
    assert url.startswith(BASE + "/")
    return url.removeprefix(BASE)


def offers_list(**raw: object) -> str | None:
    """The link to the list a search with ``raw`` arguments asks for."""
    return ServicePageLinks().offers_list(SearchOffersRequest.parse(**raw).criteria)


def test_the_page_of_a_building() -> None:
    url = ServicePageLinks().building(BuildingRef(building_slug=SLUG, city_slug="sopot"))

    assert url == BUILDING_PAGE
    assert match_page(url.removeprefix(identity.BASE_URL)) == (
        "/ceny-transakcyjne/" + "{city}/{adresy|domy}/{investRcnSlug}"
    )


@pytest.mark.parametrize(
    ("city", "slug"), [(None, SLUG), ("sopot", None), ("..", SLUG), ("sopot", " ")]
)
def test_no_page_without_its_identities(city: str | None, slug: str | None) -> None:
    assert ServicePageLinks._building_url(city, slug) is None


@pytest.mark.parametrize(
    ("slug", "city", "url"),
    [
        ("atal", "polska", PROFILES + "atal"),
        ("atal", "warszawa", identity.BASE_URL + "/ceny-ofertowe/warszawa/deweloperzy/atal"),
        ("a/b", "polska", PROFILES + "a%2Fb"),
        ("", "polska", None),
        (" ", "polska", None),
        ("..", "polska", None),
        (".", "polska", None),
    ],
)
def test_the_profile_link_is_the_developer_page_d12(slug: str, city: str, url: str | None) -> None:
    """[W] docs/discovery/pages-rsc.md: the profile route is [P] (sample ``page.developer``
    in ``warszawa``); ``polska`` as its city is [P] for the lists only."""
    assert ServicePageLinks().developer_profile(slug, CitySlug(city)) == url


def test_investment_url() -> None:
    url = ServicePageLinks._investment_url("warszawa", "atal", "nowy-targowek-vi")

    assert url == BASE + "/ceny-ofertowe/warszawa/deweloperzy/atal/nowy-targowek-vi"
    assert (
        match_page(path_of(url))
        == "/ceny-ofertowe/{city}/deweloperzy/{developerSlug}/{investmentSlug}"
    )


def test_developer_url() -> None:
    url = ServicePageLinks().developer_in("warszawa", "atal")

    assert url == BASE + "/ceny-ofertowe/warszawa/deweloperzy/atal"
    assert match_page(path_of(url)) == "/ceny-ofertowe/{city}/deweloperzy/{developerSlug}"


def test_the_list_link_keeps_the_parameters_in_order() -> None:
    url = offers_list(city="krakow", price_max=700_000, sort="price_asc") or ""

    assert url == (
        BASE + "/ceny-ofertowe/krakow/mieszkania"
        "?filterPrice=0-700000&sortBy=amount&sortOrder=asc&perPage=10"
    )
    assert match_page(path_of(url).split("?")[0]) == "/ceny-ofertowe/{city}/mieszkania"


def test_the_list_link_of_a_district_is_its_own_list() -> None:
    """[P 2026-10-31] pages-rsc.md: the district's list, at the district's slug (made from its
    name, [W]), with the query of the search as on the city's list."""
    url = offers_list(city="warszawa", district="Praga-Południe", price_dropped=True) or ""

    query: list[tuple[str, str | int]] = [("filterPriceChange", "decrease"), ("perPage", 10)]
    assert url == BASE + HttpClient.target(
        "/ceny-ofertowe/warszawa/praga-poludnie/mieszkania", query
    )
    assert match_page(path_of(url).split("?")[0]) == "/ceny-ofertowe/{city}/{district}/mieszkania"


def test_no_list_link_for_a_district_without_a_slug() -> None:
    """No address is guessed (D12): a name without a Latin letter or digit has no list."""
    assert offers_list(city="warszawa", district="Ωμέγα") is None


def test_the_list_link_of_the_first_page_has_no_page_parameter() -> None:
    """[P 2026-10-29] the service redirects ``page=1`` to the address without it: the link
    is that address, as the request is (``OffersQuery``)."""
    list_of_krakow = BASE + "/ceny-ofertowe/krakow/mieszkania"

    assert offers_list(city="krakow", page=1) == list_of_krakow + "?perPage=10"
    assert offers_list(city="krakow", page=2) == list_of_krakow + "?page=2&perPage=10"


def test_the_samples_were_captured_at_these_routes() -> None:
    """docs/discovery/samples: page.investment and page.developer."""
    investment = ServicePageLinks._investment_url("warszawa", "atal", "nowy-targowek-vi")
    assert path_of(investment or "") == "/ceny-ofertowe/warszawa/deweloperzy/atal/nowy-targowek-vi"
    assert path_of(ServicePageLinks().developer_in("warszawa", "atal") or "") == (
        "/ceny-ofertowe/warszawa/deweloperzy/atal"
    )


def test_government_stats_url_points_to_a_section() -> None:
    """[P 2026-10-29] the old route answers 308 to ``/statystyki/{location}/dane-rzadowe``,
    a [P 2026-10-31] page (docs/discovery/pages-rsc.md); the section is an id of that
    page's ``govSections``."""
    url = ServicePageLinks._government_stats_url("polska", "gus-srednia-powierzchnia")

    assert url == BASE + "/statystyki/polska/dane-rzadowe#gus-srednia-powierzchnia"
    page, fragment = path_of(url).split("#")
    assert match_page(page) == "/statystyki/{location}/dane-rzadowe"
    assert match_dump(page) is None
    assert fragment == "gus-srednia-powierzchnia"


@pytest.mark.parametrize("section", [None, "", "Gus", "a#b", "../x", "x y", "nbp?x=1", "-nbp"])
def test_government_stats_url_without_a_section_id_has_no_fragment(section: str | None) -> None:
    assert ServicePageLinks._government_stats_url("warszawa", section) == (
        BASE + "/statystyki/warszawa/dane-rzadowe"
    )


@pytest.mark.parametrize("location", [None, "", "  ", ".", "..", "\ud800"])
def test_no_government_stats_url_without_a_location(location: str | None) -> None:
    assert ServicePageLinks._government_stats_url(location, "nbp") is None


def test_government_stats_url_encodes_the_location_like_the_client() -> None:
    assert ServicePageLinks._government_stats_url("a/b?c", "nbp") == (
        BASE + "/statystyki/a%2Fb%3Fc/dane-rzadowe#nbp"
    )


@pytest.mark.parametrize(
    ("slug", "segment"),
    [
        ("kraków", "krak%C3%B3w"),
        ("łódź-ii", "%C5%82%C3%B3d%C5%BA-ii"),
        ("a b", "a%20b"),
        ("a/b", "a%2Fb"),
        ("a?b#c", "a%3Fb%23c"),
        ("a&b=c", "a%26b%3Dc"),
        ("100%", "100%25"),
    ],
)
def test_segments_are_percent_encoded_like_the_client_does(slug: str, segment: str) -> None:
    url = ServicePageLinks._investment_url("warszawa", "atal", slug)

    assert url == BASE + f"/ceny-ofertowe/warszawa/deweloperzy/atal/{segment}"
    assert urllib.parse.unquote(url.rsplit("/", 1)[1]) == slug


@pytest.mark.parametrize(
    ("city", "developer", "investment"),
    [
        (None, "atal", "smolna"),
        ("", "atal", "smolna"),
        ("  ", "atal", "smolna"),
        ("sopot", None, "smolna"),
        ("sopot", "", "smolna"),
        ("sopot", "atal", None),
        ("sopot", "atal", ""),
        ("sopot", "atal", ".."),
        ("sopot", ".", "smolna"),
        ("..", "atal", "smolna"),
        ("sopot", "atal", "\ud800"),  # a lone surrogate: cannot be encoded
        ("sopot", "\udfff", "smolna"),
    ],
)
def test_no_address_without_every_slug(
    city: str | None, developer: str | None, investment: str | None
) -> None:
    """A missing (or path-like) slug gives no address: never a guess."""
    assert ServicePageLinks._investment_url(city, developer, investment) is None
    if investment == "smolna":
        assert ServicePageLinks().developer_in(city, developer) is None


def test_addresses_have_no_rsc_token_nor_api_paths() -> None:
    urls = [
        ServicePageLinks._investment_url("warszawa", "atal", "nowy-targowek-vi"),
        ServicePageLinks().developer_in("warszawa", "atal"),
        offers_list(city="warszawa", page=2, per_page=50),
        offers_list(city="warszawa", district="Mokotów", page=2),
    ]

    for url in urls:
        assert url is not None
        assert "_rsc" not in url and "/api/" not in url
        assert url.startswith(BASE + "/ceny-ofertowe/")


def test_the_link_of_the_cities_ranking_is_its_page() -> None:
    links: RankingLinks = ServicePageLinks()
    path = "/ceny-transakcyjne/polska/miasta"

    assert links.city_ranking() == BASE + path
    assert match_page(path) == path  # [P] docs/discovery/pages-rsc.md, the city ranking
    assert match_dump(path) is None
    assert envelope("page.cities_ranking")["_request"] == f"GET {path}"


def test_the_link_is_the_public_page_of_the_city() -> None:
    url = ServicePageLinks().transaction_statistics(TransactionCity("bielsko-biala"))

    assert url == BASE + "/statystyki/bielsko-biala/transakcje"


def test_the_link_is_the_page_the_monthly_series_is_read_from() -> None:
    assert ServicePageLinks().transaction_statistics(TransactionCity("karpacz")) == (
        BASE + TransactionStatisticsApi.stats_path("karpacz")
    )


def test_the_linked_page_is_the_2_0_route_and_no_dump() -> None:
    """[P 2026-10-30] docs/discovery/pages-rsc.md: the transaction statistics of a city moved
    to ``/statystyki/{location}/transakcje`` (the old ``/mapa`` route answers 308 there); the
    page has no ``rawTransactions``, so it is no dump (the dump is an API path now)."""
    path = path_of(ServicePageLinks._transaction_stats_url("warszawa") or "")

    assert path == "/statystyki/warszawa/transakcje"
    assert match_page(path) == "/statystyki/{location}/transakcje"
    assert match_dump(path) is None
    assert match_dump(request_target("page.stats_transactions")) is not None  # the old page


@pytest.mark.parametrize("slug", [None, "", " ", ".", ".."])
def test_no_link_without_a_city(slug: str | None) -> None:
    assert ServicePageLinks._transaction_stats_url(slug) is None
