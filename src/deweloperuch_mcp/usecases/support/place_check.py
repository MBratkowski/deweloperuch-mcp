"""What a "not found" about a city means: no such place, or a place without the data
(``PlaceCheck``), in one place for every operation that takes a city."""

from deweloperuch_mcp.models.errors import DeweloperuchError, NotFoundError, ServiceBlockedError
from deweloperuch_mcp.models.values import Slug
from deweloperuch_mcp.usecases.ports import PlaceDirectory

DO_NOT_RETRY = "Nie ponawiaj; powiedz to użytkownikowi."
"""What to do about a place the service has no data for, unless the operation says more."""


class PlaceCheck:
    """``with PlaceCheck(places, city, what="statystyk rynku")``: after the service
    answered ``NotFoundError`` about ``city``, ask ``places`` whether the place exists, and
    say which it is. ``what`` is the data the service has not got, in the genitive
    („ofert”, „statystyk transakcji”); ``then`` what to do about a place without it;
    ``after_unknown`` what to add when no place was found (``None``: nothing).

    "No place found" is worded as what the lookup can tell: the dictionary it asks is
    taken for a superset of the places the tools know ([W], ``CityLookupApi``), so the
    message still covers a slug from search_locations that the service has no data for.

    One lookup, only after a ``NotFoundError`` (never after an answer with data), so a
    call that succeeds costs nothing more. When the lookup cannot tell (it fails, or the
    place it gives has another slug), the first "not found" stands unchanged: the lookup
    never masks the service's answer. A STOP of the lookup is raised, as ``ReportedAs``
    passes it: it is about the series of requests, not about this data.

    Put it outside ``ReportedAs``, which words the first "not found".
    """

    def __init__(
        self,
        places: PlaceDirectory,
        city: Slug,
        *,
        what: str,
        then: str = DO_NOT_RETRY,
        after_unknown: str | None = None,
    ) -> None:
        self._places = places
        self._city = city
        self._what = what
        self._then = then
        self._after_unknown = after_unknown

    def __enter__(self) -> None:
        return None

    def __exit__(
        self, kind: type[BaseException] | None, err: BaseException | None, _trace: object
    ) -> None:
        if not isinstance(err, NotFoundError):
            return
        message = self._message()
        if message is not None:
            raise NotFoundError(message, detail=err.detail) from err

    def _message(self) -> str | None:
        """What the "not found" was about; ``None`` when the lookup cannot tell."""
        slug = self._city.value
        try:
            place = self._places.lookup(self._city)
        except ServiceBlockedError:
            raise
        except DeweloperuchError:
            return None
        if place is None:
            unknown = (
                f"Nie znaleziono miejscowości o city_slug {slug!r}. Jeśli slug nie pochodzi z "
                "search_locations, weź go stamtąd; jeśli pochodzi, serwis nie ma dla niej tych "
                "danych: powiedz to użytkownikowi i nie ponawiaj."
            )
            return unknown if self._after_unknown is None else f"{unknown} {self._after_unknown}"
        if not place.is_named(slug):
            return None
        return (
            f"Miejscowość {place.name!r} istnieje, ale serwis nie ma dla niej {self._what}. "
            f"{self._then}"
        )
