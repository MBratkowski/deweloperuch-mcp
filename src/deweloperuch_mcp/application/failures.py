"""What a failure of the service is about, in the domain's terms (D12)."""

from collections.abc import Iterator
from contextlib import contextmanager

from deweloperuch_mcp.domain.errors import NotFoundError, ServiceError


@contextmanager
def reported_as(subject: str, *, not_found: str | None = None) -> Iterator[None]:
    """Say what an error of a port is about: ``subject`` (e.g. "Inwestycja 'smolna'").

    ``NotFoundError`` becomes ``not_found`` (default: the subject and the port's message);
    ``ServiceError`` and ``UnexpectedResponseError`` keep their type and pause with the
    subject in front. ``detail`` stays. STOP, limiter and input errors pass unchanged:
    they are about the series of requests, not about this data.
    """
    try:
        yield
    except NotFoundError as err:
        raise NotFoundError(not_found or f"{subject}: {err}", detail=err.detail) from err
    except ServiceError as err:
        raise type(err)(f"{subject}: {err}", err.pause_seconds, detail=err.detail) from err
