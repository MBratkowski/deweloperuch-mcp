"""Running a tool's operation: in a worker thread, with the server's session, its result
presented for the model, or an error result (``isError``) with the message only.

``DeweloperuchError`` -> its message, which says what to change or that the series
stopped (STOP); its ``detail`` (paths, statuses, bodies) goes only to the server log,
escaped (``consumers.shared.text``). Anything else -> a generic message; the traceback goes
to the log. The log is stderr: stdout is the protocol.
"""

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from mcp.server.mcpserver import Context
from mcp.types import CallToolResult, TextContent

from deweloperuch_mcp.bootstrap import Session
from deweloperuch_mcp.consumers.mcp.support import mcp_model
from deweloperuch_mcp.consumers.mcp.support.mcp_model import McpModel
from deweloperuch_mcp.consumers.shared.text import printable
from deweloperuch_mcp.models.errors import DeweloperuchError, ServiceBlockedError

LOGGER_NAME = "deweloperuch_mcp.mcp_server"
"""The server's log keeps the name it had before D13 (filters of the log keep working)."""

logger = logging.getLogger(LOGGER_NAME)

SessionContext = Context[Session, Any]

UNEXPECTED_ERROR = (
    "Nieoczekiwany błąd serwera MCP deweloperuch (szczegóły są w jego logu). "
    "Nie ponawiaj tego wywołania; zgłoś problem użytkownikowi."
)


def session_of(ctx: SessionContext) -> Session:
    return ctx.request_context.lifespan_context


async def run(call: Callable[[], McpModel]) -> CallToolResult:
    """``call`` in a worker thread: its result, or a tool error with the message only."""
    try:
        result = await asyncio.to_thread(call)
    except ServiceBlockedError as err:
        logger.warning("%s Szczegóły: %s", err, _detail(err))
        return _error(str(err))
    except DeweloperuchError as err:
        logger.info("%s: %s Szczegóły: %s", type(err).__name__, err, _detail(err))
        return _error(str(err))
    except Exception:
        logger.exception("Nieoczekiwany błąd narzędzia")
        return _error(UNEXPECTED_ERROR)
    return CallToolResult(
        content=[TextContent(type="text", text=mcp_model.dump_json(result))],
        structured_content=mcp_model.dump(result),
    )


def _error(message: str) -> CallToolResult:
    return CallToolResult(content=[TextContent(type="text", text=message)], is_error=True)


def _detail(err: DeweloperuchError) -> str | None:
    return None if err.detail is None else printable(err.detail)
