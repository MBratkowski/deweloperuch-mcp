"""Tests of ``deweloperuch_mcp.allowlist``."""

from deweloperuch_mcp.allowlist import match_api, match_dump, match_page


def test_the_new_channels_are_read_channels_and_city_sales_is_no_dump() -> None:
    """D15: city-sales stays on the allowlist and off ``DUMP_PATHS``."""
    assert match_api("/api/offers/city-sales/krakow") == "/api/offers/city-sales/{citySlug}"
    assert match_dump("/api/offers/city-sales/krakow") is None
    assert match_page("/ceny-ofertowe/polska/deweloperzy/atal") is not None
