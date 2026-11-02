"""``PlaceNamesDto``: the table of place names the package ships (``api/data/place_names.json``),
written offline from a saved ``GET /api/map/tx-cities`` by ``recon/place_names.py``.

``statystyki/powiat-map-stats`` names its powiats by id only and ``statystyki/gov-map-stats``
its cities by slug only; ``tx-cities`` holds both names, but it is 3.3 MB and the package
never fetches it at run time (D19). The table: ``powiats`` {id: name} (380) and ``cities``
{slug: name} (the 66 cities of ``gov-map-stats``) [P 2026-11-02,
tests/fixtures/api/tx_cities_20261102.json]. A powiat or city missing from it is shown by
its identity (``models.location_ranking.PlaceNames``).
"""

from functools import cache
from importlib.resources import files

from pydantic import ConfigDict

from deweloperuch_mcp.api.dto.dto import Dto
from deweloperuch_mcp.models.location_ranking import PlaceNames

PACKAGED = "place_names.json"
"""The table's file in ``deweloperuch_mcp/api/data/``."""


class PlaceNamesDto(Dto):
    """The packaged table (``packaged``): names by id (powiats) and by slug (cities)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    powiats: dict[int, str]
    cities: dict[str, str]

    @classmethod
    def packaged(cls) -> "PlaceNamesDto":
        """The table the package ships, read once per process."""
        return _packaged()

    def to_model(self) -> PlaceNames:
        return PlaceNames(
            powiats=self.powiats,
            cities={PlaceNames.fold(slug): name for slug, name in self.cities.items()},
        )


@cache
def _packaged() -> PlaceNamesDto:
    table = files("deweloperuch_mcp.api") / "data" / PACKAGED
    return PlaceNamesDto.model_validate_json(table.read_text(encoding="utf-8"))
