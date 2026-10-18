"""The base of every DTO (D17): the backend's JSON 1:1, tolerant to how values are typed.

Field names and nesting are the backend's (``invest``, ``sale``, ``cityMappings``...);
``to_model()`` renames them (D3). Values are kept as sent: amounts and coordinates come
as numbers or numeric strings depending on the endpoint, dates as ``YYYY-MM-DD`` or ISO
datetimes, missing text as ``""`` (docs/discovery/entities.md, "Normalizacja"). A DTO
only checks that such a value can be normalized (``Number``, ``DateText``), so the
conversions of ``to_model()`` (``Dto._number``, ``Dto._rounded``, ``Dto._exact_whole``,
``Dto._day``, ``Dto._text``) never fail on service data.

Unknown fields are ignored (the backend may add some). Fields the models rely on are
required, so a renamed or removed field fails the contract tests instead of turning
into silent ``None``. Every DTO is immutable: the client caches response bodies, not
DTOs, but nothing should mutate a parsed response anyway.
"""

import datetime as dt
import math
import re
from functools import cache
from typing import Annotated, Any, TypeVar

from pydantic import BaseModel, BeforeValidator, ConfigDict, TypeAdapter, ValidationError

from deweloperuch_mcp.models.errors import SERVICE_CHANGED, UnexpectedResponseError

M = TypeVar("M", bound=BaseModel)

_NUMERIC_TEXT = re.compile(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?")
_DATE_TEXT = re.compile(r"\d{4}-\d{2}-\d{2}")
_DATETIME_TEXT = re.compile(r"\d{4}-\d{2}-\d{2}T.+")
_QUARTER_TEXT = re.compile(r"\d{4}-Q[1-4]")
_MONTH_TEXT = re.compile(r"\d{4}-(?:0[1-9]|1[0-2])")


def _check_number(value: object) -> object:
    """A finite number, a numeric string or ``""``, returned unchanged."""
    if isinstance(value, bool):
        raise ValueError("oczekiwano liczby, a nie wartości logicznej")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("oczekiwano skończonej liczby")
        return value
    if isinstance(value, str):
        text = value.strip()
        # isfinite: "1e999" is numeric text, but float() makes it inf.
        if text and not (_NUMERIC_TEXT.fullmatch(text) and math.isfinite(float(text))):
            raise ValueError(f"oczekiwano skończonej liczby albo pustego tekstu, podano {value!r}")
        return value
    raise ValueError(f"oczekiwano liczby albo tekstu z liczbą, podano {type(value).__name__}")


def _check_date(value: object) -> object:
    """``YYYY-MM-DD``, an ISO datetime (``2025-02-25T00:00:00.000Z``) or ``""``, unchanged."""
    if not isinstance(value, str):
        raise ValueError(f"oczekiwano daty jako tekstu, podano {type(value).__name__}")
    text = value.strip()
    if not text:
        return value
    if _DATE_TEXT.fullmatch(text):
        dt.date.fromisoformat(text)  # ValueError for 2026-13-01
    elif _DATETIME_TEXT.fullmatch(text):
        dt.datetime.fromisoformat(text)
    else:
        raise ValueError(f"oczekiwano daty YYYY-MM-DD albo ISO 8601, podano {value!r}")
    return value


def _period_text(pattern: re.Pattern[str], example: str) -> Any:
    """A validator of a period as the pages send it (``example``), returned stripped."""

    def check(value: object) -> str:
        text = value.strip() if isinstance(value, str) else None
        if text is None or not pattern.fullmatch(text):
            raise ValueError(f"oczekiwano okresu w postaci {example}, podano {value!r}")
        return text

    return BeforeValidator(check)


Number = Annotated[int | float | str, BeforeValidator(_check_number)]
"""A number as the backend sends it: ``994012``, ``"994012"``, ``"55.25"`` or ``""``."""

DateText = Annotated[str, BeforeValidator(_check_date)]
"""A date as the backend sends it: ``"2026-10-03"``, ``"2025-02-25T00:00:00.000Z"``, ``""``."""

QuarterText = Annotated[str, _period_text(_QUARTER_TEXT, "2025-Q3")]
"""A quarter as the pages send it (government statistics, transactions, buildings):
``"2025-Q3"``."""

MonthText = Annotated[str, _period_text(_MONTH_TEXT, "2025-08")]
"""A month as the pages send it (government statistics, transactions): ``"2025-08"``."""


class Dto(BaseModel):
    """A DTO: ``validated`` reads one from the service's data; subclasses convert their
    values with ``_number``, ``_day`` and ``_text`` in ``to_model()``."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    @staticmethod
    def validated(model: type[M], data: Any, source: str) -> M:
        """``data`` as ``model``; a mismatch is an ``UnexpectedResponseError``.

        ``source`` (where the data came from) and the problems go to its ``detail``.
        """
        try:
            return model.model_validate(data)
        except ValidationError as err:
            raise _mismatch(err, source) from err

    @staticmethod
    def validated_rows(model: type[M], rows: Any, source: str) -> list[M]:
        """``rows`` as a list of ``model``; a mismatch is an ``UnexpectedResponseError``
        (``validated``'s message and detail)."""
        try:
            return _rows_of(model).validate_python(rows)
        except ValidationError as err:
            raise _mismatch(err, source) from err

    @staticmethod
    def _number(value: int | float | str | None) -> float | None:
        """``994012``, ``"994012"``, ``" -0.6 "`` -> float; ``""`` and ``None`` -> ``None``."""
        if value is None:
            return None
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return None
        return float(value)

    @classmethod
    def _positive(cls, value: int | float | str | None) -> float | None:
        """A price or an area as ``_number`` gives it, with 0 and less as no value: no flat
        has a price or an area of 0, and the service writes 0 where it has none
        ([P 2026-10-13] monthly statistics; [P 2026-10-15] ``city-transaction-stats``,
        tests/fixtures/api/city_tx_stats_20261015.json)."""
        found = cls._number(value)
        return found if found is not None and found > 0 else None

    @classmethod
    def _rounded(cls, value: int | float | str | None) -> int | None:
        """The nearest whole number (``"9"``, ``9.0`` -> 9, ``1.5`` -> 2); ``None`` for no
        value."""
        found = cls._number(value)
        return None if found is None else round(found)

    @classmethod
    def _exact_whole(cls, value: int | float | str | None) -> int | None:
        """A whole number as sent (``1``, ``"1"``, ``1.0`` -> 1); ``None`` for no value and
        for a fraction (``1.5``), which is no count, floor or number of rooms."""
        found = cls._number(value)
        return int(found) if found is not None and found.is_integer() else None

    @staticmethod
    def _day(value: str | None) -> dt.date | None:
        """``"2026-10-03"`` or an ISO datetime -> date (of the moment in UTC); ``""`` ->
        ``None``. The service sends event dates as UTC midnight
        (``2025-02-25T00:00:00.000Z``) [P]."""
        text_value = (value or "").strip()
        if not text_value:
            return None
        if len(text_value) == 10:
            return dt.date.fromisoformat(text_value)
        moment = dt.datetime.fromisoformat(text_value)
        if moment.tzinfo is not None:
            moment = moment.astimezone(dt.UTC)
        return moment.date()

    @staticmethod
    def _text(value: str | None) -> str | None:
        """Stripped text; ``""`` and whitespace -> ``None`` (the backend sends ``""`` for
        none)."""
        stripped = (value or "").strip()
        return stripped or None


def _mismatch(err: ValidationError, source: str) -> UnexpectedResponseError:
    problems = "; ".join(
        f"{'.'.join(str(part) for part in e['loc']) or '(całość)'}: {e['msg']}"
        for e in err.errors()[:3]
    )
    more = f" (i {err.error_count() - 3} innych)" if err.error_count() > 3 else ""
    return UnexpectedResponseError(
        f"Dane z serwisu nie pasują do kontraktu klienta (inny format). {SERVICE_CHANGED}",
        detail=f"{source}: {problems}{more}",
    )


@cache
def _rows_of(model: type[M]) -> TypeAdapter[list[M]]:
    return TypeAdapter(list[model])  # type: ignore[valid-type]
