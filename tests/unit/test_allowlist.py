"""Tests of ``deweloperuch_mcp.allowlist``."""

import pytest

from deweloperuch_mcp.allowlist import (
    LONG_CACHE_PATHS,
    match_api,
    match_dump,
    match_long_cache,
    match_page,
)


def test_the_new_channels_are_read_channels_and_city_sales_is_no_dump() -> None:
    """D15: city-sales stays on the allowlist and off ``DUMP_PATHS``."""
    assert match_api("/api/offers/city-sales/krakow") == "/api/offers/city-sales/{citySlug}"
    assert match_dump("/api/offers/city-sales/krakow") is None
    assert match_page("/ceny-ofertowe/polska/deweloperzy/atal") is not None


def test_the_routes_promoted_for_the_2_0_service_are_read_channels() -> None:
    """D20, D21: the headings the docs added on 2026-10-30 (endpoints.md, pages-rsc.md)."""
    assert match_api("/api/map/offer-snapshot/krakow") == "/api/map/offer-snapshot/{citySlug}"
    assert match_dump("/api/map/offer-snapshot/krakow") is None  # D20: aggregates only
    assert match_page("/statystyki/warszawa/transakcje") == "/statystyki/{location}/transakcje"
    assert match_page("/statystyki/7-miast/dane-rzadowe") == "/statystyki/{location}/dane-rzadowe"
    assert match_page("/ceny-ofertowe/warszawa/bemowo/mieszkania") == (
        "/ceny-ofertowe/{city}/{district}/mieszkania"
    )


@pytest.mark.parametrize(
    "path",
    [
        "/api/cities",
        "/api/city-lookup",
        "/api/city-districts",
        "/api/investments",
        "/api/developers",
        "/api/map/tx-cities",
        "/api/avg-price-trend/city/krakow",
        "/api/statystyki/powiat-map-stats",
        "/api/statystyki/gov-map-stats",
    ],
)
def test_the_nine_dictionary_and_index_routes_get_the_long_cache(path: str) -> None:
    """D19: each of the nine routes, and each is a read channel too."""
    assert match_long_cache(path)
    assert match_api(path) is not None


def test_long_cache_matcher_rejects_longer_paths() -> None:
    assert not match_long_cache("/api/cities/x")
    assert not match_long_cache("/api/citiesx")
    assert not match_long_cache("/api/avg-price-trend/city/krakow/x")
    assert not match_long_cache("/api/avg-price-trend/building/123")


def test_the_long_cache_paths_are_read_channels() -> None:
    assert all(match_api(template) == template for template in LONG_CACHE_PATHS)
