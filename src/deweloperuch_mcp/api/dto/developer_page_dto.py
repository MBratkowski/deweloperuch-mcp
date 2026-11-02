"""``DeveloperPageDto``: the developer's profile on the page
``/ceny-ofertowe/{city}/deweloperzy/{developerSlug}`` (RSC), as the 2.0 service renders it
[P 2026-10-31] (tests/fixtures/rsc/developer_*_20261031.rsc, sample
``page.developer.v2_spec``; docs/discovery/pages-rsc.md, the developer page).

D21: the page is an internal channel of the site's UI; its props may change without
notice, and a page without the developer reads as a changed service, never as an unknown
developer.

What is read, each in tests/contract/api/dto/test_developer_page_dto.py:

- the developer and its investments in the page's city (or the whole country): the props
  ``developerSlug``, ``developerName`` and ``investments`` of the element held by the prop
  ``hero``, and of no other element (another one repeats ``developerSlug``). The page's own
  ``developer`` is null, so there is no website or description. An investment's figures
  are those of its active offers (checked against the offer snapshot of Warsaw of the same
  day); ``total_offers`` counts the archived ones too (Nowy Targówek VI: 75 = the 21 active
  and 54 archived offers of its page, docs/discovery/pages-rsc.md);
- the cities: the rows of the chart ``ceny-w-miastach``, one of the page's ``spec`` props,
  found by its id. A row sums up the developer's investments in its city: ``value`` their
  price per m² weighted by their active offers, ``extra`` the active offers and the tip's
  ``inwestycje`` the number of investments, both as display text (``"60"``, ``"1 816"``,
  read by ``DeveloperCityRowDto._count``). The page of a developer in one city has no such
  chart [P 2026-10-31, Ceres Development]; a page without it is taken for such a developer
  ([W], one page seen so): its cities are then those of its investments, and the profile
  says so (``DeveloperProfile.cities_from_investments``, ``DeveloperPageDto.to_model``).

Gone since 2026-10-29: ``data {developer, investments, filteredStats, citiesStats, …}`` and
``sale``. The totals are computed from the investments (``DeveloperSummary.of``).
Not read: the other charts, ``timeline``, ``sparseBySize``, an investment's ``street``,
``min_*``, coordinates and price-change sums.

0 is no value, not a price: the service writes 0 for the averages of a developer without
active offers in a city [P 2026-10-20, 1.0 page, live: ``atal`` in ``bialystok``]
(``Dto._positive``).
"""

import logging
import re
from typing import Any, Self

from pydantic import Field, StrictFloat, StrictInt

from deweloperuch_mcp.api.dto.dto import Dto, Number
from deweloperuch_mcp.flight import NOT_FOUND_DIGEST, component_props, error_digests
from deweloperuch_mcp.models.developer_profile import (
    DeveloperCity,
    DeveloperInvestment,
    DeveloperProfile,
)
from deweloperuch_mcp.models.errors import SERVICE_CHANGED, NotFoundError, UnexpectedResponseError
from deweloperuch_mcp.models.offer import DeveloperRef
from deweloperuch_mcp.models.values import CitySlug

CITIES_CHART = "ceny-w-miastach"
"""The ``id`` of the ``spec`` prop with the developer's cities [P 2026-10-31]."""

HERO_PROPS = ("developerSlug", "developerName", "investments")
"""The props of the ``hero`` element that are read: the developer and its investments."""

REDIRECT_DIGEST = "NEXT_REDIRECT"
"""The first field of the ``digest`` of a page's redirect in its error row,
``NEXT_REDIRECT;<kind>;<path>;<status>;`` [P 2026-11-02,
tests/fixtures/rsc/developer_unknown_city_20261102.rsc]."""

INVESTMENTS_TIP = "inwestycje"
"""The ``key`` of the tip row with a city's number of investments [P 2026-10-31]."""

_DIGITS = re.compile(r"[0-9]+")
_GROUPING = str.maketrans("", "", " \u00a0\u202f")
"""Spaces that may group the thousands of a count: plain, no-break, narrow no-break."""

_log = logging.getLogger(__name__)

_LOGGED = 80
"""Characters of the service's text a log line shows."""


def _excerpt(shown: int | float | str) -> str:
    """The service's text for a log line, cut to ``_LOGGED`` characters."""
    text = str(shown)
    return text if len(text) <= _LOGGED else text[:_LOGGED] + "…"


Shown = StrictInt | StrictFloat | str | None
"""A figure as the chart shows it: display text, or a number (a flag is no figure)."""


class DeveloperInvestmentDto(Dto):
    """An investment of the profile; ``avg_*`` of its active offers. Every key is required
    (a renamed one is a changed page), each value may be null."""

    name: str
    slug: str
    status: str
    city: str | None
    city_slug: str | None
    active_offers: int | None
    total_offers: int | None
    avg_amount: Number | None
    avg_size: Number | None
    avg_price_sqm: Number | None

    def to_model(self, developer: DeveloperRef) -> DeveloperInvestment:
        """The investment of ``developer`` (the profile's owner)."""
        return DeveloperInvestment(
            investment_slug=self.slug,
            name=self.name,
            city=self._text(self.city),
            city_slug=self._text(self.city_slug),
            status=self.status,
            active_offers=self.active_offers,
            total_offers=self.total_offers,
            avg_price=self._positive(self.avg_amount),
            avg_area_m2=self._positive(self.avg_size),
            avg_price_per_m2=self._positive(self.avg_price_sqm),
            developer=developer,
        )


class CityTipRowDto(Dto):
    key: str
    value: Shown


class CityTipDto(Dto):
    """The tip of a city's row: labelled values (``cena``, ``oferty``, ``inwestycje``)."""

    rows: list[CityTipRowDto]

    def value(self, key: str) -> int | float | str | None:
        return next((row.value for row in self.rows if row.key == key), None)


class DeveloperCityRowDto(Dto):
    """A row of the chart of cities: one city of the developer. Every key is required (a
    renamed one is a changed chart), each value may be null; a count whose text is no
    count is no count (``_count``), not an error."""

    key: str
    label: str
    value: Number | None
    extra: Shown
    tip: CityTipDto | None

    def to_model(self) -> DeveloperCity:
        return DeveloperCity(
            city=self.label,
            city_slug=self.key,
            investments=self._count(self.tip.value(INVESTMENTS_TIP) if self.tip else None),
            active_offers=self._count(self.extra),
            avg_price_per_m2=self._positive(self.value),
        )

    @staticmethod
    def _count(shown: int | float | str | None) -> int | None:
        """A count as the page shows it: ``"60"``, a count of thousands grouped with a
        no-break space (``"1 816"``) [P 2026-10-31,
        tests/fixtures/rsc/developer_dom_development_warszawa_20261031.rsc], also with a
        plain or narrow no-break space, or a whole number. Anything else is no count
        (``None``); a value other than empty text is logged (a WARNING: the chart may have
        changed)."""
        if shown is None:
            return None
        if isinstance(shown, str):
            digits = shown.translate(_GROUPING)
            found = int(digits) if _DIGITS.fullmatch(digits) else None
        else:
            found = int(shown) if shown >= 0 and float(shown).is_integer() else None
        if found is None and str(shown).strip():
            _log.warning("Wykres miast dewelopera: %r to nie liczba, pomijam ją.", _excerpt(shown))
        return found


class CitiesChartViewDto(Dto):
    rows: list[DeveloperCityRowDto]


class CitiesChartViewsDto(Dto):
    """The chart's views; it has one, under the key ``""`` [P 2026-10-31] (no switches)."""

    default: CitiesChartViewDto = Field(alias="")


class CitiesChartDto(Dto):
    """The ``spec`` prop ``ceny-w-miastach`` (sample ``page.developer.v2_spec``): every city of
    the developer, whatever the page's city, the highest price per m² first."""

    views: CitiesChartViewsDto

    def to_model(self) -> tuple[DeveloperCity, ...]:
        return tuple(row.to_model() for row in self.views.default.rows)


class DeveloperPageDto(Dto):
    """The developer page's data: the ``hero`` element's props and the chart of cities,
    ``None`` when the page has none."""

    developerSlug: str
    developerName: str
    investments: list[DeveloperInvestmentDto]
    cities: CitiesChartDto | None

    @classmethod
    def from_payload(cls, payload: str | bytes, *, path: str, country: str | None = None) -> Self:
        """The developer, its investments and its cities, from the page at ``path``.

        The developer and its investments are the props of the first element held by a
        prop ``hero``; a name counts when its value is not null and no ``$…`` reference, and
        ``investments`` when it is a list [P 2026-10-31]. ``NotFoundError`` for the page of
        a developer the service does not know (Next.js's 404 marker [P 2026-10-31]) and for
        a city's page that sends the reader on to ``country``, the developer's page for the
        whole country (``None`` on that page itself); ``UnexpectedResponseError`` for a page
        without them and without either.
        """
        hero: dict[str, Any] | None = None
        chart: dict[str, Any] | None = None
        names: list[str] = []
        for name, value in component_props(payload):
            if isinstance(value, dict | list) and name not in names:
                names.append(name)
            if name == "hero" and hero is None and cls._is_element(value):
                hero = value[3]
            elif name == "spec" and chart is None and cls._is_cities_chart(value):
                chart = value
        found = {name: value for name, value in (hero or {}).items() if cls._is_data(name, value)}
        absent = [name for name in HERO_PROPS if name not in found]
        if absent:
            raise cls._without_developer(payload, path, absent, names, country)
        return Dto.validated(cls, {**found, "cities": chart}, f"{path} (profil dewelopera)")

    def to_model(self, city: CitySlug) -> DeveloperProfile:
        """The profile in ``city`` (the page's): its investments in the service's order,
        every city of the developer."""
        owner = DeveloperRef(developer_slug=self.developerSlug, name=self.developerName)
        investments = tuple(item.to_model(owner) for item in self.investments)
        # [W] a page without the chart of cities is the page of a developer in one city: the
        # one page seen so (Ceres Development, one investment, in Warsaw [P 2026-10-31],
        # tests/fixtures/rsc/developer_ceres_warszawa_20261031.rsc). Its cities are then
        # those of its investments, summed up as the summary is.
        cities = (
            self.cities.to_model()
            if self.cities is not None
            else DeveloperCity.of_investments(investments)
        )
        return DeveloperProfile(
            developer=owner,
            city=city,
            investments=investments,
            cities=cities,
            cities_from_investments=self.cities is None,
        )

    @staticmethod
    def _redirects_to(digest: str, target: str) -> bool:
        """``digest`` is a redirect (``NEXT_REDIRECT;<kind>;<path>;<status>;``) to ``target``."""
        fields = digest.split(";")
        return len(fields) >= 3 and fields[0] == REDIRECT_DIGEST and fields[2] == target

    @staticmethod
    def _is_element(value: object) -> bool:
        """A client element ``["$", "$L<id>", key, {props}]``."""
        return (
            isinstance(value, list)
            and len(value) >= 4
            and value[0] == "$"
            and isinstance(value[1], str)
            and value[1].startswith("$L")
            and isinstance(value[3], dict)
        )

    @staticmethod
    def _is_cities_chart(value: object) -> bool:
        return isinstance(value, dict) and value.get("id") == CITIES_CHART

    @staticmethod
    def _is_data(name: str, value: object) -> bool:
        """``value`` is data of the ``hero`` prop ``name``: a list for ``investments``; for
        a name, a value that is not null and no reference of the stream (a string starting
        with ``$``; a text that starts with ``$`` is sent escaped as ``$$``, so it is skipped
        too)."""
        if name == "investments":
            return isinstance(value, list)
        is_reference = isinstance(value, str) and value.startswith("$")
        return name in HERO_PROPS and value is not None and not is_reference

    @staticmethod
    def _without_developer(
        payload: str | bytes, path: str, absent: list[str], names: list[str], country: str | None
    ) -> NotFoundError | UnexpectedResponseError:
        """The page of a developer the service does not know (Next.js's 404 marker), the page
        of a city the service shows nothing of the developer in (a redirect to ``country``),
        or a page that changed; ``names`` are the props with data the page has."""
        lacks = "brak propsów " + ", ".join(repr(name) for name in absent)
        digests = error_digests(payload)
        if NOT_FOUND_DIGEST in digests:
            return NotFoundError(
                "Serwis nie zna żądanych danych (strona nie istnieje).",
                detail=f"{path}: {lacks}, strona zgłasza {NOT_FOUND_DIGEST}",
            )
        # D21 (exception for T39): a city's page whose payload redirects to the same
        # developer's page for the whole country reads as "not found"; every other redirect,
        # in the payload or over HTTP (transport), stays a change of the service. Seen for a
        # city the service does not know [P 2026-11-02,
        # tests/fixtures/rsc/developer_unknown_city_20261102.rsc]; a known place where the
        # developer has no offers is "not found" too [P 2026-11-02, live e2e
        # test_developer_in_a_known_place_without_its_offers, `krakowiany`] (which marker it
        # carried was not recorded). The use case asks whether the place exists.
        if country is not None and any(
            DeveloperPageDto._redirects_to(digest, country) for digest in digests
        ):
            return NotFoundError(
                "Serwis nie ma tej strony (przekierowuje do strony dewelopera w całej Polsce).",
                detail=f"{path}: {lacks}, strona przekierowuje do {country}",
            )
        data = ", ".join(names[:10]) or "brak"
        return UnexpectedResponseError(
            f"Na stronie serwisu brakuje oczekiwanych danych. {SERVICE_CHANGED}",
            detail=f"{path}: {lacks} (propsy z danymi: {data})",
        )
