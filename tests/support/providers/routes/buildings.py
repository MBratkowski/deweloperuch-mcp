"""respx routes of a building of the price register, with the bodies of the samples.

- ``BUILDING``: ``23-marca-79c-sopot``, sample ``api.tx_visible`` (3 of its 86 units);
- ``TREND``: the trend around it. The one sample of a trend (``api.avg_trend_building``)
  was captured for another building (583284); it is a real answer of the service all
  the same, so it answers for this building too.
"""

from typing import Any

import respx

from support.providers.samples import body, request_target
from support.providers.service import BASE

SLUG = "23-marca-79c-sopot"


BUILDING_ID = 1354
"""The sample's building number: the trend is asked for by it."""


BUILDING = BASE + request_target("api.tx_visible")


TREND = BASE + f"/api/avg-price-trend/building/{BUILDING_ID}"


UNKNOWN_BUILDING = "nieistniejacy-budynek"


BUILDING_PAGE = BASE + "/ceny-transakcyjne/sopot/adresy/" + SLUG


def building_routes(
    router: respx.MockRouter, building: Any = None
) -> tuple[respx.Route, respx.Route]:
    """The building (default: the sample) and the trend around it."""
    return (
        router.get(BUILDING).respond(
            200, json=body("api.tx_visible") if building is None else building
        ),
        router.get(TREND).respond(200, json=body("api.avg_trend_building")),
    )
