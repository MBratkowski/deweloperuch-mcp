"""``CityLookupDto``: ``GET /api/city-lookup?slug=&source=transactions`` (docs/discovery/
endpoints.md, ``city-lookup``), a place of the transactions dictionary by its slug.

- A known place: ``{"city": <name>, "city_slug": <slug>}`` [P 2026-10-30, sample
  ``api.city_lookup.slug_transactions``; P 2026-11-01, a village, sample
  ``api.city_lookup.village_transactions``]; the name is the register's (``Ignatki-osiedle``).
- An unknown place: a 200 with both fields null [P 2026-11-01 for a name, sample
  ``api.city_lookup.unknown``; P 2026-11-02 for a slug,
  tests/fixtures/api/city_lookup_unknown_slug_20261102.json].

Both keys are required (a renamed one is a changed answer). One field null and the other
not was never seen: it is no answer the client can read (``UnexpectedResponseError``),
like a name that is empty, longer than the service's 100 characters or with control
characters (the name goes into a message for a model).
"""

from typing import Annotated, Self

from pydantic import AfterValidator, StringConstraints, model_validator

from deweloperuch_mcp.api.dto.dto import Dto
from deweloperuch_mcp.models.place import Place


def _printable(name: str) -> str:
    if not name.isprintable():
        raise ValueError("nazwa miejscowości ze znakami sterującymi")
    return name


PlaceName = Annotated[
    str, StringConstraints(min_length=1, max_length=100), AfterValidator(_printable)
]
"""A place's name as the service writes it: 1 to 100 printable characters."""

PlaceSlug = Annotated[str, StringConstraints(pattern=r"^[a-z0-9-]{1,100}$")]
"""A place's slug as the service writes it: ``[a-z0-9-]``, at most 100."""


class CityLookupDto(Dto):
    """The answer about one slug: a place, or both fields null."""

    city: PlaceName | None
    city_slug: PlaceSlug | None

    @model_validator(mode="after")
    def _both_or_neither(self) -> Self:
        if (self.city is None) != (self.city_slug is None):
            raise ValueError("city i city_slug: jedno puste, drugie nie")
        return self

    def to_model(self) -> Place | None:
        """The place, ``None`` when the dictionary does not know it."""
        if self.city is None or self.city_slug is None:
            return None
        return Place(name=self.city, slug=self.city_slug)
