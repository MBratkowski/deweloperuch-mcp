"""``McpModel``: the base of every MCP tool result (D6, D17), how a result is dumped for
the model (``dump``, ``dump_json``), and the descriptions of the fields several tools'
results share. Capability-agnostic support of the presenters
(``consumers/mcp/presenters``).
"""

import json
from typing import Any, ClassVar

from pydantic import BaseModel, ConfigDict

PRICE = "Cena ofertowa w PLN (nie transakcyjna)."
AREA = "Metraż w m²."
PRICE_PER_M2 = "Cena za m² w PLN (price / area_m2)."
STATUS = "active (aktualna) albo archived (wycofana)."
CHANGE_SINCE_START = "Zmiana ceny od pierwszej zaobserwowanej, w PLN (ujemna = tańsza)."
CHANGE_SINCE_START_PCT = "Zmiana ceny od pierwszej zaobserwowanej, w procentach (ujemna = tańsza)."
LAST_CHANGE_KIND = "increase, decrease albo no_change."
LAST_CHANGE_PCT = "Ostatnia zmiana ceny w procentach."
# The values are [P] (docs/discovery/entities.md, SaleEvent.event_type); whether a price
# change is an `offer` event or a type of its own is [H], so no "first price" here.
EVENT_KIND = "offer (cena w ofercie), archived (wycofanie), restored (powrót)."


INVESTMENT_URL = "Strona inwestycji na deweloperuch.pl: podaj ją użytkownikowi jako link."
DEVELOPER_URL = "Profil dewelopera na deweloperuch.pl: podaj go użytkownikowi jako link."
LIST_URL = (
    "Ta lista ofert na deweloperuch.pl (te same filtry, sortowanie i strona): podaj ją "
    "użytkownikowi jako link."
)

# Class docstrings would become schema descriptions for the model: comments instead.


class McpModel(BaseModel):
    # Fields of the domain model not declared here are dropped (extra="ignore").
    model_config = ConfigDict(frozen=True, extra="ignore")

    # Top-level fields `dump` keeps when they are None (required in the schema).
    keep_null: ClassVar[frozenset[str]] = frozenset()


def dump(result: McpModel) -> dict[str, Any]:
    """The structured result: JSON values without ``null`` fields, except ``keep_null``."""
    present = result.model_dump(mode="json", exclude_none=True)
    return {
        name: present.get(name)
        for name in type(result).model_fields
        if name in present or name in result.keep_null
    }


def dump_json(result: McpModel) -> str:
    """The same as compact JSON text."""
    return json.dumps(dump(result), ensure_ascii=False, separators=(",", ":"))
