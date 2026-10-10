"""Errors the package raises on purpose; ``str(err)`` tells the user or the model what to do.

One hierarchy for the client and the services, so the CLI and the MCP server (S1b)
handle errors without importing the client (D6)::

    DeweloperuchError
    ├── InvalidInputError        wrong argument; the message says how to fix it
    ├── NotFoundError            no such investment, offer, page
    ├── ServiceBlockedError      STOP: 401, 403, Cloudflare challenge; end the series
    │   └── RateLimitedError     STOP: 429; ``pause_seconds`` recorded in the limiter
    ├── ServiceError             5xx, network, redirect, other 4xx, body too big or too slow
    │   └── UnexpectedResponseError   a 2xx whose data does not match the contract
    ├── LimiterWaitError         the shared limiter asks for a longer pause than allowed;
    │                            nothing was sent
    └── SessionClosedError       the session was closed; nothing was sent

Nothing is retried automatically (CLAUDE.md): after ``ServiceBlockedError`` stop and
report it to the user; after ``ServiceError`` with ``pause_seconds`` wait at least that
long.
"""


class DeweloperuchError(Exception):
    """Base class of every error the package raises on purpose."""


class InvalidInputError(DeweloperuchError):
    """An argument is out of range or malformed; nothing was sent."""


class NotFoundError(DeweloperuchError):
    """The service does not know the requested object (HTTP 404 or missing in the data)."""


class ServiceBlockedError(DeweloperuchError):
    """401, 403 or a Cloudflare challenge: stop the series, do not retry, tell the user."""


class RateLimitedError(ServiceBlockedError):
    """429: stop the series; the shared limiter waits ``pause_seconds`` before the next one."""

    def __init__(self, message: str, pause_seconds: float) -> None:
        super().__init__(message)
        self.pause_seconds = pause_seconds


class ServiceError(DeweloperuchError):
    """The service did not give a usable answer; nothing was retried.

    ``pause_seconds``: the pause the shared limiter recorded (502/503/504), else ``None``.
    """

    def __init__(self, message: str, pause_seconds: float | None = None) -> None:
        super().__init__(message)
        self.pause_seconds = pause_seconds


class UnexpectedResponseError(ServiceError):
    """A 2xx whose data does not match the contract (not JSON, missing prop, other shape).

    Usually the service changed after a deploy: run the drift check (flow C).
    """


class SessionClosedError(DeweloperuchError):
    """The session (its HTTP client) was closed; nothing was sent. Open a new one."""


class LimiterWaitError(DeweloperuchError):
    """The next request is allowed only after ``wait_seconds``; nothing was sent."""

    def __init__(self, message: str, wait_seconds: float) -> None:
        super().__init__(message)
        self.wait_seconds = wait_seconds
