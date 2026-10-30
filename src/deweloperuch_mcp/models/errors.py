"""Errors the package raises on purpose; ``str(err)`` tells the user or the model what to do.

The domain's own errors (D13): value objects raise them for wrong input, entities and
use cases for what is missing, the adapters of the ports for what the service did. One
hierarchy for every layer, so the CLI and the MCP server handle errors without knowing
where they came from::

    DeweloperuchError
    ├── InvalidInputError        wrong argument; the message says how to fix it
    │   └── InvalidValueError    a value the domain refuses (which, why, what was given)
    ├── NotFoundError            no such investment, offer, page
    ├── ServiceBlockedError      STOP: 401, 403, Cloudflare challenge, or a STOP that
    │   │                        any process recorded earlier; end the series
    │   └── RateLimitedError     STOP: 429; ``pause_seconds`` recorded in the limiter
    ├── ServiceError             5xx, network, redirect, other 4xx, body too big or too slow
    │   └── UnexpectedResponseError   a 2xx whose data does not match the contract
    ├── LimiterWaitError         the shared limiter asks for a longer pause than allowed;
    │                            nothing was sent
    └── SessionClosedError       the session was closed; nothing was sent

Nothing is retried automatically (CONTRIBUTING.md): after ``ServiceBlockedError`` stop and
report it to the user; after ``ServiceError`` with ``pause_seconds`` wait at least that
long.

``str(err)`` is for the user or the model: what happened, in domain terms, and what to
do. It never carries service paths, prop names or response bodies (an answer of the
service is not text to show a model). Those go to ``err.detail``, for logs and the CLI,
which escape every non-printable character when they show it (``consumers.shared.text``): text
from the service never reaches a terminal as control sequences.

Plain Python, like the rest of the domain. ``deweloperuch_mcp.errors`` re-exports
everything here for the code that imports it from there.

A value the domain refuses raises ``InvalidValueError``: which value, which rule, what
was given, in the domain's words. Naming the CLI's and the MCP server's parameters and
the operation to call instead is the application's job (``usecases.support.arguments``).
"""

from dataclasses import dataclass
from enum import StrEnum

SERVICE_CHANGED = (
    "Serwis mógł się zmienić po aktualizacji: ponawianie nie pomoże, zgłoś to użytkownikowi."
)
"""What to do about data that does not match the contract (``UnexpectedResponseError``)."""


class DeweloperuchError(Exception):
    """Base class of every error the package raises on purpose.

    ``detail``: technical details (path, status, an excerpt of the body...), ``None``
    when there are none. Never part of ``str(err)``. It may hold text of the service as
    received: whoever shows it escapes it (``consumers.shared.text.printable``).
    """

    def __init__(self, message: str, *, detail: str | None = None) -> None:
        super().__init__(message)
        self.detail = detail


class InvalidInputError(DeweloperuchError):
    """An argument is out of range or malformed; nothing was sent."""


class ValueName(StrEnum):
    """What a refused value was meant to be, in the domain's words."""

    QUERY = "szukany tekst"
    CITY = "miasto"
    INVESTMENT = "inwestycja"
    DEVELOPER = "deweloper"
    STATISTICS_LOCATION = "lokalizacja statystyk"
    OFFER = "oferta"
    AMOUNT = "kwota"
    AREA = "metraż"
    PRICE_FROM = "cena od"
    PRICE_TO = "cena do"
    PRICE_RANGE = "zakres cen"
    AREA_FROM = "metraż od"
    AREA_TO = "metraż do"
    AREA_RANGE = "zakres metrażu"
    PRICE_PER_M2 = "cena za m²"
    PRICE_PER_M2_FROM = "cena za m² od"
    PRICE_PER_M2_TO = "cena za m² do"
    PRICE_PER_M2_RANGE = "zakres cen za m²"
    DISTRICT = "dzielnica"
    PRICE_DROPPED = "tylko oferty tańsze niż na początku"
    OFFER_STATUS = "status ofert"
    PAGE = "strona wyników"
    PAGE_SIZE = "liczba ofert na stronie"
    SORT = "kolejność ofert"
    OFFERS_LIMIT = "liczba ofert w wyniku"
    INVESTMENTS_LIMIT = "liczba inwestycji w wyniku"
    TOP_DEVELOPERS = "liczba deweloperów w wyniku"
    HISTORY = "historia cen"
    DATASET = "zestaw danych"
    PERIODS = "liczba okresów"
    DEVELOPER_NAME = "nazwa dewelopera"
    DEVELOPER_MATCHES = "liczba znalezionych deweloperów"
    INVESTMENTS_CITY = "miasto inwestycji"
    INVESTMENT_NAME = "nazwa inwestycji"
    INVESTMENT_SORT = "kolejność inwestycji"
    TRANSACTIONS_CITY = "miasto statystyk transakcji"
    GRANULARITY = "długość okresu"
    RANKING_LEVEL = "poziom rankingu"
    RANKING_ORDER = "kolejność rankingu"
    RANKING_LIMIT = "liczba pozycji rankingu"
    MIN_TRANSACTIONS = "najmniejsza liczba transakcji"
    BUILDING = "budynek"
    UNITS_LIMIT = "liczba lokali w wyniku"
    TREND = "trend cen w okolicy"
    LATITUDE = "szerokość geograficzna"
    LONGITUDE = "długość geograficzna"
    VALUED_AREA = "metraż wycenianego mieszkania"
    ADDRESS = "adres"
    COMPARABLES_LIMIT = "liczba transakcji porównawczych w wyniku"


@dataclass(frozen=True)
class WholeNumber:
    """A whole number from ``low`` to ``high`` (in ``unit``, if it has one)."""

    low: int
    high: int
    unit: str | None = None

    def check(self, name: ValueName, value: object) -> int:
        """``value`` if it is a whole number (not ``True`` nor ``False``) in the range;
        otherwise an ``InvalidValueError`` of ``name`` under this rule."""
        if (
            isinstance(value, int)
            and not isinstance(value, bool)
            and self.low <= value <= self.high
        ):
            return value
        raise InvalidValueError(name, self, value)

    def refusal(self) -> str:
        """A value against this rule, in the domain's words (``InvalidValueError``)."""
        unit = f" {self.unit}" if self.unit else ""
        return f"oczekiwano liczby całkowitej z zakresu {self.low}–{self.high}{unit}"


@dataclass(frozen=True)
class OneOf:
    choices: tuple[str | int, ...]

    def refusal(self) -> str:
        """A value against this rule, in the domain's words (``InvalidValueError``)."""
        return f"oczekiwano jednej z wartości {', '.join(map(str, self.choices))}"


@dataclass(frozen=True)
class SlugText:
    """Lowercase ASCII letters, digits and hyphens: how the service writes identities."""

    def refusal(self) -> str:
        """A value against this rule, in the domain's words (``InvalidValueError``)."""
        return "oczekiwano małych liter bez polskich znaków, cyfr i myślników"


@dataclass(frozen=True)
class TextLength:
    low: int
    high: int

    def refusal(self) -> str:
        """A value against this rule, in the domain's words (``InvalidValueError``)."""
        return f"oczekiwano od {self.low} do {self.high} znaków"


@dataclass(frozen=True)
class TrueOrFalse:
    def check(self, name: ValueName, value: object) -> bool:
        """``value`` if it is ``True`` or ``False``; otherwise an ``InvalidValueError`` of
        ``name`` under this rule."""
        if not isinstance(value, bool):
            raise InvalidValueError(name, self, value)
        return value

    def refusal(self) -> str:
        """A value against this rule, in the domain's words (``InvalidValueError``)."""
        return "oczekiwano true albo false"


@dataclass(frozen=True)
class OneCity:
    """One city, not the whole country: what is asked for belongs to a single city."""

    def refusal(self) -> str:
        """A value against this rule, in the domain's words (``InvalidValueError``)."""
        return "oczekiwano jednego miasta, a nie całej Polski"


@dataclass(frozen=True)
class LowNotAboveHigh:
    """The start of a range above its end."""

    low: int
    high: int

    def refusal(self) -> str:
        """A value against this rule, in the domain's words (``InvalidValueError``)."""
        return f"początek ({self.low}) jest większy niż koniec ({self.high})"


@dataclass(frozen=True)
class NumberBetween:
    """A finite number, not only a whole one, from ``low`` to ``high`` (in ``unit``)."""

    low: float
    high: float
    unit: str | None = None

    def refusal(self) -> str:
        """A value against this rule, in the domain's words (``InvalidValueError``)."""
        unit = f" {self.unit}" if self.unit else ""
        return f"oczekiwano liczby z zakresu {self.low:g}–{self.high:g}{unit}"


Rule = (
    WholeNumber
    | OneOf
    | SlugText
    | TextLength
    | TrueOrFalse
    | OneCity
    | LowNotAboveHigh
    | NumberBetween
)


class InvalidValueError(InvalidInputError):
    """A value the domain refuses: which one (``value``), the rule it broke (``rule``) and
    what was given (``given``).

    ``str(err)`` says it in the domain's words; the application words it for the caller
    with the names of its parameters (``usecases.support.arguments``).
    """

    def __init__(self, value: ValueName, rule: Rule, given: object) -> None:
        super().__init__(f"{value}: {rule.refusal()}, podano {given!r}.")
        self.value = value
        self.rule = rule
        self.given = given


class NotFoundError(DeweloperuchError):
    """The service does not know the requested object (HTTP 404 or missing in the data)."""


class ServiceBlockedError(DeweloperuchError):
    """401, 403 or a Cloudflare challenge: stop the series, do not retry, tell the user.

    Also raised, without sending anything, while the shared limiter holds a STOP that any
    process (this package or ``recon/``) recorded earlier.
    """


class RateLimitedError(ServiceBlockedError):
    """429: stop the series; the shared limiter waits ``pause_seconds`` before the next one.

    After a 429 recorded earlier, ``pause_seconds`` is what is left of its pause.
    """

    def __init__(self, message: str, pause_seconds: float, *, detail: str | None = None) -> None:
        super().__init__(message, detail=detail)
        self.pause_seconds = pause_seconds


class ServiceError(DeweloperuchError):
    """The service did not give a usable answer; nothing was retried.

    ``pause_seconds``: the pause the shared limiter recorded (502/503/504), else ``None``.
    """

    def __init__(
        self, message: str, pause_seconds: float | None = None, *, detail: str | None = None
    ) -> None:
        super().__init__(message, detail=detail)
        self.pause_seconds = pause_seconds


class UnexpectedResponseError(ServiceError):
    """A 2xx whose data does not match the contract (not JSON, missing prop, other shape), or
    a read channel the service no longer has (``HttpClient.get``, ``gone``).

    Usually the service changed after a deploy: run the drift check (flow C).
    """


class SessionClosedError(DeweloperuchError):
    """The session (its HTTP client) was closed; nothing was sent. Open a new one."""


class LimiterWaitError(DeweloperuchError):
    """The next request is allowed only after ``wait_seconds``; nothing was sent."""

    def __init__(self, message: str, wait_seconds: float, *, detail: str | None = None) -> None:
        super().__init__(message, detail=detail)
        self.wait_seconds = wait_seconds
