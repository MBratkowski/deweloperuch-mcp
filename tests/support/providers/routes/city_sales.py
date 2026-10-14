"""respx routes of ``city-sales``: the real bodies (tests/fixtures/api/) with their headers."""

import respx

from support.providers.rsc import CITY_SALES

CITY_SALES_PATH = "/api/offers/city-sales/"


CITY_SALES_HEADERS = {
    "Content-Type": "application/json",
    "Cache-Control": "public, max-age=28800, s-maxage=300, stale-while-revalidate=3600",
}


def city_sales_routes(router: respx.MockRouter) -> dict[str, respx.Route]:
    """The real ``city-sales`` of Sopot and Kraków (tests/fixtures/api/), byte for byte,
    with their headers; ``polska`` answers 400 as the service does [P 2026-10-10]."""
    routes = {
        city: router.get(path=CITY_SALES_PATH + city).respond(
            200, content=path.read_bytes(), headers=CITY_SALES_HEADERS
        )
        for city, path in CITY_SALES.items()
    }
    routes["polska"] = router.get(path=CITY_SALES_PATH + "polska").respond(
        400, json={"error": "Invalid citySlug"}
    )
    return routes
