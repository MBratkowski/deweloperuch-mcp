"""The districts of a city as the service lists them for its offers (D13), and how a
district asked for by name is found among them."""

import re
from dataclasses import dataclass

from deweloperuch_mcp.models.values import DistrictName

_POLISH_LETTERS = str.maketrans("ąćęłńóśźż", "acelnoszz")
_NOT_LETTER_OR_DIGIT = re.compile(r"[^a-z0-9]+")


def _folded(name: str) -> str:
    """``name`` lowercase, its Polish letters without their marks, without spaces, dashes
    or other characters: ``Praga - Północ`` -> ``pragapolnoc``.

    Only the nine Polish letters are mapped, on purpose: the models may not import
    ``unicodedata`` (tests/architecture), while the slug of ``OffersQuery._district_slug``
    strips every mark (NFKD). The two agree on Polish names; another letter with a mark
    (``ü``) is dropped here from both names compared, not mapped to its base letter.
    """
    return _NOT_LETTER_OR_DIGIT.sub("", name.lower().translate(_POLISH_LETTERS))


@dataclass(frozen=True)
class District:
    """A district of a city with offers: its name and the slug of its list's address, as
    the service gives them."""

    name: str
    slug: str

    def is_named(self, asked: DistrictName) -> bool:
        """Whether ``asked`` names this district, regardless of case, Polish letters,
        spaces and dashes (``ŚRÓDMIEŚCIE``, ``srodmiescie``, ``Praga Północ``). A name that
        folds to nothing names no district."""
        folded = _folded(asked.text)
        return bool(folded) and folded == _folded(self.name)
