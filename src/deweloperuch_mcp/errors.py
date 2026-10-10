"""Errors the package raises on purpose; ``str(err)`` tells the user or the model what to do.

One hierarchy for the client and the services, so the CLI and the MCP server (S1b)
handle errors without importing the client (D6)::

    DeweloperuchError
    ├── InvalidInputError        wrong argument; the message says how to fix it
    ├── NotFoundError            no such investment, offer, page
    ├── ServiceBlockedError      STOP: 401, 403, Cloudflare challenge, or a STOP that
    │   │                        any process recorded earlier; end the series
    │   └── RateLimitedError     STOP: 429; ``pause_seconds`` recorded in the limiter
    ├── ServiceError             5xx, network, redirect, other 4xx, body too big or too slow
    │   └── UnexpectedResponseError   a 2xx whose data does not match the contract
    ├── LimiterWaitError         the shared limiter asks for a longer pause than allowed;
    │                            nothing was sent
    └── SessionClosedError       the session was closed; nothing was sent

Nothing is retried automatically (CLAUDE.md): after ``ServiceBlockedError`` stop and
report it to the user; after ``ServiceError`` with ``pause_seconds`` wait at least that
long.

``str(err)`` is for the user or the model: what happened, in domain terms, and what to
do. It never carries service paths, prop names or response bodies (an answer of the
service is not text to show a model). Those go to ``err.detail``, for logs and the CLI,
with every non-printable character escaped (``printable``): text from the service never
reaches a terminal as control sequences.
"""

SERVICE_CHANGED = (
    "Serwis mógł się zmienić po aktualizacji: ponawianie nie pomoże, zgłoś to użytkownikowi."
)
"""What to do about data that does not match the contract (``UnexpectedResponseError``)."""


def printable(text: str) -> str:
    """``text`` with every non-printable character as an escape, ``repr``-like.

    ``"a\\x1b]0;x\\x07"`` -> ``"a\\\\x1b]0;x\\\\x07"``: no terminal control sequences (OSC,
    CSI), no line breaks, no invisible bidi controls. Printable text, Polish letters
    included, stays as it is.
    """
    return "".join(char if char.isprintable() else _escape(char) for char in text)


def _escape(char: str) -> str:
    code = ord(char)
    if code < 0x100:
        return f"\\x{code:02x}"
    if code < 0x10000:
        return f"\\u{code:04x}"
    return f"\\U{code:08x}"


class DeweloperuchError(Exception):
    """Base class of every error the package raises on purpose.

    ``detail``: technical details (path, status, an excerpt of the body...), ``None``
    when there are none. Never part of ``str(err)``; non-printable characters escaped
    here, so no caller can forget it.
    """

    def __init__(self, message: str, *, detail: str | None = None) -> None:
        super().__init__(message)
        self.detail = None if detail is None else printable(detail)


class InvalidInputError(DeweloperuchError):
    """An argument is out of range or malformed; nothing was sent."""


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
    """A 2xx whose data does not match the contract (not JSON, missing prop, other shape).

    Usually the service changed after a deploy: run the drift check (flow C).
    """


class SessionClosedError(DeweloperuchError):
    """The session (its HTTP client) was closed; nothing was sent. Open a new one."""


class LimiterWaitError(DeweloperuchError):
    """The next request is allowed only after ``wait_seconds``; nothing was sent."""

    def __init__(self, message: str, wait_seconds: float, *, detail: str | None = None) -> None:
        super().__init__(message, detail=detail)
        self.wait_seconds = wait_seconds
