"""Tests of ``deweloperuch_mcp.allowlist``."""

from deweloperuch_mcp.allowlist import match_api, match_dump, match_page


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
