"""``ValuationQuery``: what to value -> the address of ``GET /api/standalone-valuation`` [P]
(docs/discovery/endpoints.md, "5. Valuation").

The parameters of the sample ``api.standalone_val``, in its order: ``area``, ``lat``,
``lng`` and, when given, ``address``; numbers without trailing zeros (``50``,
``52.2297``).
"""

from deweloperuch_mcp.models.valuation import AREA_DECIMALS, ValuationSubject

Query = list[tuple[str, str | int]]

PATH = "/api/standalone-valuation"

COORDINATE_DECIMALS = 6
"""Degrees to 0.000001 (about 0.1 m); the sample sends four decimals (52.2297)."""


class ValuationQuery:
    """The address of the valuation of ``subject``: ``path()`` and ``params()``."""

    def __init__(self, subject: ValuationSubject) -> None:
        self._subject = subject

    def path(self) -> str:
        return PATH

    def params(self) -> Query:
        """``area``, ``lat``, ``lng`` and ``address`` (only when given), as the sample's
        request [P] has them."""
        subject = self._subject
        params: Query = [
            # [W] docs/discovery/endpoints.md: the sample sends a whole area (50); a fraction
            # (48.78) is sent as is. The service's own valuations use fractional areas
            # (page.offer_report: data.area 55.25 [P]), not through this request.
            ("area", self._decimal(subject.area.value, AREA_DECIMALS)),
            ("lat", self._decimal(subject.point.lat, COORDINATE_DECIMALS)),
            ("lng", self._decimal(subject.point.lng, COORDINATE_DECIMALS)),
        ]
        if subject.address is not None:
            # [W] the request of the sample sends ``address`` and the service accepts it [P];
            # what it changes in the result is not known. The point is lat/lng.
            params.append(("address", subject.address.text))
        return params

    @staticmethod
    def _decimal(value: float, places: int) -> str:
        """``50.0`` -> ``50``, ``52.2297`` -> ``52.2297``: at most ``places`` decimals."""
        return f"{value:.{places}f}".rstrip("0").rstrip(".")
