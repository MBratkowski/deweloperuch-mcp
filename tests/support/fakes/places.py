"""``PlaceDirectory`` in memory: its answer for each slug, or the failure of every lookup."""

from collections.abc import Mapping
from typing import TYPE_CHECKING

from deweloperuch_mcp.models.place import Place
from deweloperuch_mcp.models.values import Slug
from deweloperuch_mcp.usecases import ports

VILLAGE = Place(name="Ignatki-osiedle", slug="ignatki-osiedle")
"""A village the service knows (sample api.city_lookup.village_transactions); the tests
pair it with a mocked "not found" of a tool."""


def unknown_place_message(slug: str) -> str:
    """What a tool says after a "not found" about ``slug`` when no place was found
    (``PlaceCheck``), without an operation's own ending."""
    return (
        f"Nie znaleziono miejscowości o city_slug {slug!r}. Jeśli slug nie pochodzi z "
        "search_locations, weź go stamtąd; jeśli pochodzi, serwis nie ma dla niej tych "
        "danych: powiedz to użytkownikowi i nie ponawiaj."
    )


class FakePlaces:
    """Answers ``answers[slug]`` (no place for a slug it does not hold); ``failure`` (if
    given) is raised by every lookup. ``calls`` lists the slugs looked up."""

    def __init__(
        self, answers: Mapping[str, Place] | None = None, *, failure: Exception | None = None
    ) -> None:
        self.answers = dict(answers or {})
        self.failure = failure
        self.calls: list[str] = []

    @classmethod
    def knowing(cls, *places: Place) -> "FakePlaces":
        """Knows ``places``, each by its own slug."""
        return cls({place.slug: place for place in places})

    def lookup(self, slug: Slug) -> Place | None:
        self.calls.append(slug.value)
        if self.failure is not None:
            raise self.failure
        return self.answers.get(slug.value)


if TYPE_CHECKING:  # mypy checks that the fake is the port it stands in for
    _places: ports.PlaceDirectory = FakePlaces()
