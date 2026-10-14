"""Developers found by a part of their name (D3, D13), and how much of the search is shown.

A match carries the ``developer_slug`` a developer's profile takes. The source
(``ports.DeveloperSearch``) is asked for at most ``MatchCount`` developers and says
how many match in all and whether it has more (``DeveloperMatches``); the result keeps
the cut explicit (D4) and trusts the source's total only when it fits what came.
"""

from dataclasses import dataclass
from typing import Self

from deweloperuch_mcp.models.errors import InvalidValueError, TextLength, ValueName, WholeNumber
from deweloperuch_mcp.models.values import QUERY_MAX, QUERY_MIN

DEFAULT_MATCHES = 5
"""Developers a search shows unless asked otherwise: what the service's own search box
asks for [P] (docs/discovery/endpoints.md, sample ``api.developers_q``)."""

MAX_MATCHES = 20
"""The most a search shows. [W] the service honours counts up to it as it does for its
location search (at least 20 [P]); the result is cut to the count anyway."""


@dataclass(frozen=True)
class DeveloperName:
    """A part of a developer's name: ``QUERY_MIN``..``QUERY_MAX`` characters, Polish
    letters included."""

    text: str

    def __post_init__(self) -> None:
        given: object = self.text  # a dataclass does not check the type it is given
        if not isinstance(given, str) or not QUERY_MIN <= len(given) <= QUERY_MAX:
            raise self.refused(given)

    @classmethod
    def parse(cls, value: object) -> Self:
        """``value`` without spaces around it; a refusal repeats ``value`` as given."""
        text = value.strip() if isinstance(value, str) else ""
        if not QUERY_MIN <= len(text) <= QUERY_MAX:
            raise cls.refused(value)
        return cls(text)

    @staticmethod
    def refused(value: object) -> InvalidValueError:
        return InvalidValueError(ValueName.DEVELOPER_NAME, TextLength(QUERY_MIN, QUERY_MAX), value)

    def __str__(self) -> str:
        return self.text


@dataclass(frozen=True)
class MatchCount:
    """How many developers a search shows: 1..``MAX_MATCHES``."""

    value: int = DEFAULT_MATCHES

    def __post_init__(self) -> None:
        WholeNumber(1, MAX_MATCHES).check(ValueName.DEVELOPER_MATCHES, self.value)

    @classmethod
    def parse(cls, value: object) -> Self:
        return cls(value)  # type: ignore[arg-type]  # checked in __post_init__


@dataclass(frozen=True, kw_only=True)
class DeveloperMatch:
    """A developer whose name matches; ``developer_slug`` identifies its profile."""

    developer_slug: str
    name: str
    offer_count: int | None = None
    """Offers of the developer, as the service counts them."""


@dataclass(frozen=True)
class DeveloperMatches:
    """What the source gave: its matches in its order, every match it knows of
    (``total``; ``None`` when it does not say) and whether it has more than it gave."""

    items: tuple[DeveloperMatch, ...]
    total: int | None = None
    more: bool = False


@dataclass(frozen=True)
class DeveloperSearchResult:
    """At most ``count`` developers matching ``name`` (D4: the cut is explicit).

    ``truncated``: more developers match than shown, because the source says so (it has
    more, or a total above what is shown) or because it gave more than ``count``.
    ``total``: every match, from the source when its total fits what came (not below it,
    and above it when the source has more); otherwise unknown (``None``) for a truncated
    result and the matches shown for a complete one.
    """

    name: DeveloperName
    count: MatchCount
    items: tuple[DeveloperMatch, ...]
    truncated: bool
    total: int | None

    @classmethod
    def of(cls, name: DeveloperName, count: MatchCount, matches: DeveloperMatches) -> Self:
        items = matches.items[: count.value]
        came = len(matches.items)
        known = matches.total
        if known is not None and (known < came or (matches.more and known == came)):
            known = None  # does not fit what came
        truncated = matches.more or came > len(items) or (known is not None and known > came)
        if known is None:
            known = None if truncated else len(items)
        return cls(name=name, count=count, items=items, truncated=truncated, total=known)

    @property
    def returned(self) -> int:
        return len(self.items)
