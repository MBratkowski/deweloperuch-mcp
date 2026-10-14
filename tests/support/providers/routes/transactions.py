"""respx routes of the transaction statistics: ``api.monthly_tx`` (Warsaw, months) and
``api.avg_trend_city`` (Warsaw, quarters).
"""

from typing import Any

import respx

from support.providers.samples import body, request_target
from support.providers.service import BASE

MONTHLY = BASE + request_target("api.monthly_tx")
"""The request of the monthly sample: flats of Warsaw."""


CITY_TREND = BASE + request_target("api.avg_trend_city")
"""The request of the quarterly sample: Warsaw."""


MONTHLY_PATH = "/api/monthly-transaction-stats"


TREND_PATH = "/api/avg-price-trend/city/"


def transaction_routes(
    router: respx.MockRouter, monthly: Any = None, quarterly: Any = None
) -> tuple[respx.Route, respx.Route]:
    """Both endpoints for any city: the samples (Warsaw), or ``monthly``/``quarterly``."""
    return (
        router.get(path=MONTHLY_PATH).respond(
            200, json=body("api.monthly_tx") if monthly is None else monthly
        ),
        router.route(method="GET", path__startswith=TREND_PATH).respond(
            200, json=body("api.avg_trend_city") if quarterly is None else quarterly
        ),
    )


def transaction_answer(status: int, **kw: Any) -> Any:
    """Both endpoints answer ``status`` with ``kw`` (a router for the golden cases)."""

    def answer(router: respx.MockRouter) -> None:
        router.get(path=MONTHLY_PATH).respond(status, **kw)
        router.route(method="GET", path__startswith=TREND_PATH).respond(status, **kw)

    return answer
