"""A place the service knows: a city, a town or a village, by its slug and its name.

What a tool says when the service has no data for a slug: whether the place exists at all
(``usecases.ports.PlaceDirectory``) tells a wrong slug from a place without data.
"""

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class Place:
    """A place with its name as the service writes it (``Ignatki-osiedle``) and its slug
    (``ignatki-osiedle``)."""

    name: str
    slug: str

    def is_named(self, slug: str) -> bool:
        """``slug`` is this place's own slug, not another one the service matched to it."""
        return self.slug == slug
