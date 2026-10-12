"""Addresses of the service's public pages (D12, 2026-10-11): one builder, [P] routes only.

The routes are the headings of docs/discovery/pages-rsc.md (the package allowlist holds
the same ones); the list of offers is the page the client requests, without ``_rsc``.
"""

import urllib.parse
from collections.abc import Iterator
from pathlib import Path

import pytest
import respx

import operations
from deweloperuch_mcp import bootstrap, identity
from deweloperuch_mcp.allowlist import match_page
from deweloperuch_mcp.infrastructure.deweloperuch import links
from deweloperuch_mcp.infrastructure.deweloperuch.transport import build_target
from deweloperuch_mcp.throttle import RequestLimiter
from rsc_fixtures import offers_payload
from service_mocks import stats_routes

BASE = identity.BASE_URL


def path_of(url: str) -> str:
    assert url.startswith(BASE + "/")
    return url.removeprefix(BASE)


# --- the routes -----------------------------------------------------------------------------------


def test_investment_url() -> None:
    url = links.investment_url("warszawa", "atal", "nowy-targowek-vi")

    assert url == BASE + "/ceny-ofertowe/warszawa/deweloperzy/atal/nowy-targowek-vi"
    assert (
        match_page(path_of(url))
        == "/ceny-ofertowe/{city}/deweloperzy/{developerSlug}/{investmentSlug}"
    )


def test_developer_url() -> None:
    url = links.developer_url("warszawa", "atal")

    assert url == BASE + "/ceny-ofertowe/warszawa/deweloperzy/atal"
    assert match_page(path_of(url)) == "/ceny-ofertowe/{city}/deweloperzy/{developerSlug}"


def test_offers_list_url_keeps_the_parameters_in_order() -> None:
    params: list[tuple[str, str | int]] = [
        ("filterPrice", "0-700000"),
        ("sortBy", "amount"),
        ("sortOrder", "asc"),
        ("page", 1),
        ("perPage", 10),
    ]

    url = links.offers_list_url("krakow", params)

    assert url == (
        BASE + "/ceny-ofertowe/krakow/mieszkania"
        "?filterPrice=0-700000&sortBy=amount&sortOrder=asc&page=1&perPage=10"
    )
    assert match_page(path_of(url).split("?")[0]) == "/ceny-ofertowe/{city}/mieszkania"


def test_offers_list_url_encodes_the_query_as_the_client_does() -> None:
    """The client's query builder (``build_target``): a space is %20, not +."""
    params: list[tuple[str, str | int]] = [("filterDistrict", "Mokotów Górny"), ("q", "a+b&c")]

    url = links.offers_list_url("warszawa", params)

    assert url == BASE + build_target("/ceny-ofertowe/warszawa/mieszkania", params)
    assert url.endswith("?filterDistrict=Mokot%C3%B3w%20G%C3%B3rny&q=a%2Bb%26c")


def test_offers_list_url_of_the_whole_country() -> None:
    assert links.offers_list_url("polska", [("page", 1), ("perPage", 10)]) == (
        BASE + "/ceny-ofertowe/polska/mieszkania?page=1&perPage=10"
    )


def test_the_samples_were_captured_at_these_routes() -> None:
    """docs/discovery/samples: page.investment and page.developer."""
    assert path_of(links.investment_url("warszawa", "atal", "nowy-targowek-vi") or "") == (
        "/ceny-ofertowe/warszawa/deweloperzy/atal/nowy-targowek-vi"
    )
    assert path_of(links.developer_url("warszawa", "atal") or "") == (
        "/ceny-ofertowe/warszawa/deweloperzy/atal"
    )


def test_government_stats_url_points_to_a_section() -> None:
    url = links.government_stats_url("polska", "gus-srednia-powierzchnia")

    assert url == BASE + "/statystyki/statystyki-rzadowe/polska#gus-srednia-powierzchnia"
    page, fragment = path_of(url).split("#")
    assert match_page(page) == "/statystyki/statystyki-rzadowe/{location}"
    assert fragment == "gus-srednia-powierzchnia"


@pytest.mark.parametrize("section", [None, "", "Gus", "a#b", "../x", "x y", "nbp?x=1", "-nbp"])
def test_government_stats_url_without_a_section_id_has_no_fragment(section: str | None) -> None:
    assert links.government_stats_url("warszawa", section) == (
        BASE + "/statystyki/statystyki-rzadowe/warszawa"
    )


@pytest.mark.parametrize("location", [None, "", "  ", ".", "..", "\ud800"])
def test_no_government_stats_url_without_a_location(location: str | None) -> None:
    assert links.government_stats_url(location, "nbp") is None


def test_government_stats_url_encodes_the_location_like_the_client() -> None:
    assert links.government_stats_url("a/b?c", "nbp") == (
        BASE + "/statystyki/statystyki-rzadowe/a%2Fb%3Fc#nbp"
    )


# --- segments -------------------------------------------------------------------------------------


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
    url = links.investment_url("warszawa", "atal", slug)

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
    assert links.investment_url(city, developer, investment) is None
    if investment == "smolna":
        assert links.developer_url(city, developer) is None


def test_addresses_have_no_rsc_token_nor_api_paths() -> None:
    urls = [
        links.investment_url("warszawa", "atal", "nowy-targowek-vi"),
        links.developer_url("warszawa", "atal"),
        links.offers_list_url("warszawa", [("page", 2), ("perPage", 50)]),
    ]

    for url in urls:
        assert url is not None
        assert "_rsc" not in url and "/api/" not in url
        assert url.startswith(BASE + "/ceny-ofertowe/")


# --- the list link is the request search_offers sends ---------------------------------------------


@pytest.fixture
def session(tmp_path: Path) -> Iterator[bootstrap.Session]:
    limiter = RequestLimiter(tmp_path, min_interval=0, testing_only_allow_fast_interval=True)
    with bootstrap.Session(limiter=limiter) as opened:
        yield opened


@pytest.mark.parametrize(
    "arguments",
    [
        {"city": "warszawa"},
        {"city": "polska", "page": 3, "per_page": 50},
        {
            "city": "krakow",
            "price_min": 400_000,
            "price_max": 700_000,
            "area_min": 40,
            "sort": "price_desc",
            "page": 2,
            "per_page": 100,
        },
    ],
)
def test_the_list_link_is_the_request_without_its_token(
    session: bootstrap.Session, arguments: dict[str, object]
) -> None:
    with respx.mock(assert_all_mocked=True) as router:
        route = router.route(method="GET", path__startswith="/ceny-ofertowe/").respond(
            200, content=offers_payload(), headers={"Content-Type": "text/x-component"}
        )

        result = operations.search_offers(session, **arguments)

    sent = route.calls.last.request.url
    query = sent.query.decode()
    assert query.endswith(f"&_rsc={sent.params['_rsc']}")
    assert (
        result.list_url
        == f"{BASE}{sent.raw_path.decode().split('?')[0]}?{query.rsplit('&_rsc=', 1)[0]}"
    )


def test_the_statistics_link_is_the_request_without_its_token(session: bootstrap.Session) -> None:
    """The page the service read, at the section of the dataset (D12)."""
    with respx.mock(assert_all_called=False, assert_all_mocked=True) as router:
        route = stats_routes(router)["warszawa"]

        result = operations.get_government_statistics(session, "warszawa", "unemployment")

    sent = route.calls.last.request.url
    assert sent.query.decode() == f"_rsc={sent.params['_rsc']}"
    assert result.stats_url == f"{BASE}{sent.raw_path.decode().split('?')[0]}#gus-bezrobocie"
    assert result.stats_url is not None and "_rsc" not in result.stats_url
