"""The package's errors, re-exported from the domain (``deweloperuch_mcp.domain.errors``),
and ``printable`` (``deweloperuch_mcp.interfaces.text``).

D13 moved the hierarchy into the domain; this module keeps the import path that the CLI,
the MCP server, the tests and the documentation use.
"""

from deweloperuch_mcp.domain.errors import (
    SERVICE_CHANGED,
    DeweloperuchError,
    InvalidInputError,
    LimiterWaitError,
    NotFoundError,
    RateLimitedError,
    ServiceBlockedError,
    ServiceError,
    SessionClosedError,
    UnexpectedResponseError,
)
from deweloperuch_mcp.interfaces.text import printable

__all__ = [
    "SERVICE_CHANGED",
    "DeweloperuchError",
    "InvalidInputError",
    "LimiterWaitError",
    "NotFoundError",
    "RateLimitedError",
    "ServiceBlockedError",
    "ServiceError",
    "SessionClosedError",
    "UnexpectedResponseError",
    "printable",
]
