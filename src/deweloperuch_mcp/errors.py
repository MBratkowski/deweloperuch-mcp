"""The package's errors, re-exported from the models (``deweloperuch_mcp.models.errors``),
and ``printable`` (``deweloperuch_mcp.consumers.shared.text``).

D13 moved the hierarchy into the domain (D16: ``models``); this module keeps the import
path that the CLI, the MCP server, the tests and the documentation use.
"""

from deweloperuch_mcp.consumers.shared.text import printable
from deweloperuch_mcp.models.errors import (
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
