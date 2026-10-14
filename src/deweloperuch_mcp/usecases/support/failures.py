"""What a failure of the service is about, in the models' terms (D12)."""

from deweloperuch_mcp.models.errors import NotFoundError, ServiceError


class ReportedAs:
    """``with ReportedAs(subject, not_found=...)``: say what an error of a port is about,
    ``subject`` (e.g. "Inwestycja 'smolna'").

    ``NotFoundError`` becomes ``not_found`` (default: the subject and the port's message);
    ``ServiceError`` and ``UnexpectedResponseError`` keep their type and pause with the
    subject in front. ``detail`` stays. STOP, limiter and input errors pass unchanged:
    they are about the series of requests, not about this data.
    """

    def __init__(self, subject: str, *, not_found: str | None = None) -> None:
        self._subject = subject
        self._not_found = not_found

    def __enter__(self) -> None:
        return None

    def __exit__(
        self, kind: type[BaseException] | None, err: BaseException | None, _trace: object
    ) -> None:
        if isinstance(err, NotFoundError):
            message = self._not_found or f"{self._subject}: {err}"
            raise NotFoundError(message, detail=err.detail) from err
        if isinstance(err, ServiceError):
            message = f"{self._subject}: {err}"
            raise type(err)(message, err.pause_seconds, detail=err.detail) from err
