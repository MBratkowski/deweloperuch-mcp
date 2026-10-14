"""respx routes of the investment search (a city's list, a name's matches), with the bodies
of the samples.
"""

from typing import Any

import respx

from support.providers.samples import body

CITY_INVESTMENTS = "/api/map/investments"


NAMED_INVESTMENTS = "/api/investments"


def investment_search_routes(
    router: respx.MockRouter, city: Any = None, names: Any = None
) -> tuple[respx.Route, respx.Route]:
    """The investments of a city (default: Sopot's two, sample api.map_investments_sopot)
    for any ``citySlug``, and the matches of a name (default: "nowy targ", sample
    api.investments_q) for any ``q`` and ``limit``."""
    return (
        router.get(path=CITY_INVESTMENTS).respond(
            200, json=body("api.map_investments_sopot") if city is None else city
        ),
        router.get(path=NAMED_INVESTMENTS).respond(
            200, json=body("api.investments_q") if names is None else names
        ),
    )
