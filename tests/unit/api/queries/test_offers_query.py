"""Tests of ``deweloperuch_mcp.api.queries.offers_query``."""

import re
from typing import Any

import pytest

from deweloperuch_mcp.api.http.transport import HttpClient
from deweloperuch_mcp.api.queries import offers_query
from deweloperuch_mcp.api.queries.offers_query import SORT_PARAMS, OffersQuery
from deweloperuch_mcp.models.values import AmountPln, AreaM2, OfferSort, PricePerM2Pln
from deweloperuch_mcp.usecases.search_offers import SearchOffersRequest
from support.builders.offers import OFFERS_QUERY_CASES, district_pages


def query_of(params: list[tuple[str, str | int]]) -> str:
    return HttpClient.target("", params).removeprefix("?")


def search(**given: Any) -> OffersQuery:
    return OffersQuery(SearchOffersRequest.parse(**given).criteria)


@pytest.mark.parametrize(("given", "query"), OFFERS_QUERY_CASES)
def test_the_query_of_the_criteria(given: dict[str, Any], query: str) -> None:
    assert query_of(search(city="krakow", **given).params()) == query


@pytest.mark.parametrize(
    ("given", "query"),
    [({}, "perPage=10"), ({"page": 1}, "perPage=10"), ({"page": 2}, "page=2&perPage=10")],
)
def test_the_first_page_is_sent_without_a_page_parameter(given: dict[str, Any], query: str) -> None:
    """[P 2026-10-29] docs/discovery/pages-rsc.md: the service answers ``page=1`` with 308 to
    the same address without it (and without ``_rsc``), so the first page is the address
    without ``page``."""
    assert query_of(search(city="krakow", **given).params()) == query


def test_a_city_is_the_list_of_its_offers() -> None:
    """[P 2026-10-31] pages-rsc.md: ``/ceny-ofertowe/{city}/mieszkania``."""
    assert search(city="krakow").path() == "/ceny-ofertowe/krakow/mieszkania"


def client_slugify(name: str) -> str:
    """The client's slugify of an offer's name [P z kodu] (pages-rsc.md, the offer report):
    Polish letters to ASCII, lowercase, everything but ``[a-z0-9\\s-]`` removed, spaces to
    ``-``."""
    text = name.lower().translate(str.maketrans("ąćęłńóśźż", "acelnoszz"))
    return re.sub(r"\s", "-", re.sub(r"[^a-z0-9\s-]", "", text))


@pytest.mark.parametrize(("city", "name", "path"), district_pages())
def test_a_district_is_the_list_at_the_slug_the_service_gives_it(
    city: str, name: str, path: str
) -> None:
    """[W] the slug made of a district's name without a request is the service's own for the
    36 districts it named with one on 2026-10-31 (``builders.offers.district_pages``): 18 of
    Warszawa as the whole path of their list (``href`` of the prop ``items``) and, as a slug
    of ``city-districts``, the same 18 and the 18 of Kraków."""
    assert search(city=city, district=name).path() == path


def test_the_districts_of_the_service_have_polish_letters_and_several_words() -> None:
    """54 pairs, 36 districts: the slugs of ``city-districts`` for Warszawa are those of the
    links of its offers list."""
    pages = district_pages()
    names = {name for _, name, _ in pages}

    assert len(pages) == 54
    assert len(set(pages)) == len({(city, name) for city, name, _ in pages}) == 36
    assert {"Praga-Południe", "Łagiewniki-Borek Fałęcki", "Śródmieście", "Żoliborz"} <= names
    assert {"Prądnik Biały", "Wzgórza Krzesławickie", "Bieżanów-Prokocim"} <= names


def test_the_clients_slugify_gives_the_same_slugs_but_parts_on_punctuation() -> None:
    """[P z kodu] the client's slugify of offer names and the rule here agree on the 36
    districts; they part on punctuation and on runs of separators, which no district seen
    has. Which one the service would use for such a name is not known [H]."""
    for city, name, path in district_pages():
        assert f"/ceny-ofertowe/{city}/{client_slugify(name)}/mieszkania" == path
    assert client_slugify("Św.Katarzyny") == "swkatarzyny"
    assert client_slugify("Praga - Południe") == "praga---poludnie"


@pytest.mark.parametrize(
    ("name", "slug"),
    [
        (" Mokotów ", "mokotow"),
        ("MOKOTÓW", "mokotow"),
        ("mokotow", "mokotow"),
        ("ŁAGIEWNIKI-BOREK FAŁĘCKI", "lagiewniki-borek-falecki"),
        # The rule's own choices for what the service never sent [H]: one hyphen for each
        # run of other characters, none at the ends.
        ("Praga - Południe", "praga-poludnie"),
        ("Św.Katarzyny", "sw-katarzyny"),
        ("Os. Kosmonautów", "os-kosmonautow"),
        ("(Wola)", "wola"),
        # digits stay, as in ``city-districts`` slugs ([a-z0-9-], [P 2026-10-30])
        ("Osiedle 1000-lecia", "osiedle-1000-lecia"),
    ],
)
def test_the_slug_of_a_name_written_otherwise(name: str, slug: str) -> None:
    assert search(city="warszawa", district=name).path() == (
        f"/ceny-ofertowe/warszawa/{slug}/mieszkania"
    )


@pytest.mark.parametrize("name", ["--", "..", "日本", "Ωμέγα"])
def test_a_district_name_without_a_latin_letter_or_digit_has_no_list(name: str) -> None:
    """The service writes districts as ``[a-z0-9-]`` slugs [P 2026-10-31]: such a name has
    none, so there is no address to ask (and no link)."""
    assert search(city="warszawa", district=name).path() is None


def test_the_district_list_takes_the_parameters_of_the_city_list() -> None:
    """[W] T73: the district route was requested without parameters; the search sends the
    same ones as to the city list (tests/e2e/test_live_mcp.py: a district with a price
    filter, every row within the range)."""
    found = search(city="warszawa", district="Mokotów", price_max=900_000, sort="price_asc", page=2)

    assert found.path() == "/ceny-ofertowe/warszawa/mokotow/mieszkania"
    assert query_of(found.params()) == (
        "filterPrice=0-900000&sortBy=amount&sortOrder=asc&page=2&perPage=10"
    )


def test_the_district_is_no_parameter_any_more() -> None:
    """[P 2026-10-31] pages-rsc.md: ``filterDistrict`` (the name or the slug) on the city list
    answers a page without ``sales``."""
    params = search(city="warszawa", district="Mokotów").params()

    assert [name for name, _ in params] == ["perPage"]


def test_open_ends_are_the_ui_sentinels() -> None:
    """[P z kodu] pages-rsc.md: the UI's own ends of an open range; this mapping owns them
    (the domain's open end is ``None``). They equal the largest values the domain accepts,
    so every closed range the domain lets through is also within them."""
    assert (offers_query.OPEN_LOW, offers_query.PRICE_SENTINEL, offers_query.AREA_SENTINEL) == (
        0,
        99_999_999,
        9_999,
    )
    assert (offers_query.PRICE_SENTINEL, offers_query.AREA_SENTINEL) == (AmountPln.MAX, AreaM2.MAX)
    # [P z kodu] the price-per-m² one; what the 2.0 server does with any sentinel is [W]
    # (tests/e2e/test_live_mcp.py).
    assert offers_query.PRICE_PER_M2_SENTINEL == PricePerM2Pln.MAX == 999_999


def test_every_order_has_its_sort_parameters() -> None:
    """[P 2026-10-31] pages-rsc.md: ``amount`` descending. [P 2026-10-10] (1.0): ``amount``
    both ways; ``price_per_sqm``, ``size`` and ``start_amount_difference_percent``
    ascending. Every other order, and every one but ``amount`` descending on 2.0, is [W]
    (commented in ``SORT_PARAMS``; the live suite checks each order)."""
    assert dict(SORT_PARAMS) == {
        OfferSort.PRICE_ASC: ("amount", "asc"),
        OfferSort.PRICE_DESC: ("amount", "desc"),
        OfferSort.PRICE_PER_M2_ASC: ("price_per_sqm", "asc"),
        OfferSort.PRICE_PER_M2_DESC: ("price_per_sqm", "desc"),
        OfferSort.AREA_ASC: ("size", "asc"),
        OfferSort.AREA_DESC: ("size", "desc"),
        OfferSort.BIGGEST_DROP: ("start_amount_difference_percent", "asc"),
    }
