"""Arguments as models send them: the rules of the MCP input schemas (D11).

Integers also as text of digits only; ``""`` and ``null`` mean "not given" or the default;
choices are trimmed. Bounds sit on the number itself, so the schema shows them.
"""

import re
from typing import Annotated, Literal

from pydantic import BeforeValidator, Field

from deweloperuch_mcp.domain.values import BROWSABLE_PAGES, AmountPln, AreaM2

McpPerPage = Literal[10, 50]
"""Page sizes of ``search_offers`` in MCP: [P] values that keep a result readable."""

# One rule for every number: JSON integers, or text of digits only ("10", " 10 "), never
# "10.0" nor true/false. Optional arguments: "" and null mean "not given"; arguments with
# a default: null means the default. Choices are trimmed (" price_asc ").
_INTEGER = re.compile(r"[+-]?\d{1,18}")


def _whole_number(value: object) -> object:
    """``"10"`` -> ``10`` (models sometimes send numbers as text)."""
    if isinstance(value, bool):
        raise ValueError("oczekiwano liczby całkowitej, a nie true/false")
    if isinstance(value, str):
        text = value.strip()
        if not _INTEGER.fullmatch(text):
            raise ValueError(f"oczekiwano liczby całkowitej zapisanej cyframi, podano {value!r}")
        return int(text)
    return value


def _blank_is_none(value: object) -> object:
    """``""`` for an optional argument means "not given"; other text is trimmed."""
    if isinstance(value, str):
        return value.strip() or None
    return value


def _optional_whole_number(value: object) -> object:
    blank = _blank_is_none(value)
    return None if blank is None else _whole_number(blank)


def whole_or(default: int) -> BeforeValidator:
    """A whole number; ``null`` means ``default``."""
    return BeforeValidator(lambda value: _whole_number(default if value is None else value))


def null_is(default: object) -> BeforeValidator:
    return BeforeValidator(lambda value: default if value is None else value)


def _trimmed(value: object) -> object:
    return value.strip() if isinstance(value, str) else value


WholeNumber = BeforeValidator(_whole_number)
OptionalWholeNumber = BeforeValidator(_optional_whole_number)
OptionalChoice = BeforeValidator(_blank_is_none)
Choice = BeforeValidator(_trimmed)

# Bounds on the number itself, so the schema shows them inside `anyOf` with null.
# (A BeforeValidator before Field(ge=...) would leave raw "ge"/"le" in the schema.)
Price = Annotated[int, Field(ge=0, le=AmountPln.MAX)]
Area = Annotated[int, Field(ge=0, le=AreaM2.MAX)]
Page = Annotated[int, Field(ge=1, le=BROWSABLE_PAGES)]
OfferId = Annotated[int, Field(ge=1)]
