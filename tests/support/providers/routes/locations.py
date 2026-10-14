"""respx routes of the location search, with the bodies of the samples."""

from typing import Any

import respx

from support.providers.samples import body


def location_routes(
    router: respx.MockRouter, cities: dict[str, Any] | None = None
) -> tuple[respx.Route, respx.Route]:
    """The location search: the samples, or ``cities`` instead of the cities' sample."""
    return (
        router.get(path="/api/cities").respond(200, json=cities or body("api.cities_q")),
        router.get(path="/api/location-search").respond(200, json=body("api.location_search")),
    )
