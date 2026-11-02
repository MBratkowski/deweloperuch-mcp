"""``DistrictDirectory`` in memory: the districts it is given (by default the real ones of
Warszawa, ``builders.districts``), or the error it is given; it records the cities asked.
``FakeDistrictLists``: an ``OfferCatalog`` that knows the lists of some districts only."""

from collections.abc import Mapping
from typing import TYPE_CHECKING

from deweloperuch_mcp.models.district import District
from deweloperuch_mcp.models.errors import NotFoundError
from deweloperuch_mcp.models.offer import OfferSearchCriteria, OfferSearchPage
from deweloperuch_mcp.models.price_history import PriceEvent
from deweloperuch_mcp.models.values import CitySlug, OfferId
from deweloperuch_mcp.usecases import ports
from support.builders.districts import warszawa_districts


class FakeDistrictDirectory:
    def __init__(
        self, listed: tuple[District, ...] | None = None, error: Exception | None = None
    ) -> None:
        self.listed = warszawa_districts() if listed is None else listed
        self.error = error
        self.calls: list[str] = []

    def districts(self, city: CitySlug) -> tuple[District, ...]:
        self.calls.append(city.value)
        if self.error is not None:
            raise self.error
        return self.listed


class FakeDistrictLists:
    """``OfferCatalog`` whose only lists are those of the districts ``listed`` (by the text a
    search gives): ``page`` for them; any other district, or the city's list, is not found,
    as the service's 404 marker [P 2026-10-31]. ``errors``: what the search of a district
    raises instead. Records the district of every search."""

    def __init__(
        self,
        page: OfferSearchPage,
        listed: frozenset[str] = frozenset(),
        errors: Mapping[str, Exception] | None = None,
    ) -> None:
        self.page = page
        self.listed = listed
        self.errors = dict(errors or {})
        self.searched: list[str | None] = []

    def search(self, criteria: OfferSearchCriteria) -> OfferSearchPage:
        district = None if criteria.district is None else criteria.district.text
        self.searched.append(district)
        if district in self.errors:
            raise self.errors[district]
        if district in self.listed:
            return self.page
        raise NotFoundError("Serwis nie zna żądanych danych.", detail="404")

    def price_events(self, offer_id: OfferId) -> tuple[PriceEvent, ...]:
        raise AssertionError("a search reads no price events")


if TYPE_CHECKING:  # mypy checks that each fake is the port it stands in for
    _district_directory: ports.DistrictDirectory = FakeDistrictDirectory()
    _offer_catalog: ports.OfferCatalog = FakeDistrictLists(
        OfferSearchPage(items=(), total=0, page=1, per_page=10)
    )
