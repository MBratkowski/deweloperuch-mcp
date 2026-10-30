"""Reading a ``GET /api/*`` endpoint as JSON (channel A, D1): ``JsonEndpoint``.

Only read endpoints from docs/discovery/endpoints.md, called with the query parameters
their samples were captured with; the adapters name them.
"""

import json
from collections.abc import Collection
from typing import Any, TypeVar

from pydantic import BaseModel

from deweloperuch_mcp.api.dto.dto import Dto
from deweloperuch_mcp.api.http.transport import NOT_FOUND, HttpClient, Reply
from deweloperuch_mcp.http_policy import is_html
from deweloperuch_mcp.models.errors import SERVICE_CHANGED, UnexpectedResponseError

M = TypeVar("M", bound=BaseModel)

JSON_HEADERS = {"Accept": "application/json"}


class JsonEndpoint:
    """``target`` (a path with its encoded query) read through ``http`` with the JSON
    headers: the one JSON path of the client. ``unknown``: the statuses that mean the
    service does not know what was asked for, ``gone``: those that mean the endpoint is no
    longer there (``HttpClient.get``)."""

    def __init__(
        self,
        http: HttpClient,
        target: str,
        *,
        unknown: Collection[int] = (NOT_FOUND,),
        gone: Collection[int] = (),
    ) -> None:
        self._http = http
        self._target = target
        self._unknown = unknown
        self._gone = gone

    def get(self, model: type[M]) -> M:
        """The reply as ``model``; a mismatch is an ``UnexpectedResponseError``."""
        path = self._target.split("?", 1)[0]
        return self._http.get(
            self._target,
            headers=JSON_HEADERS,
            decode=lambda reply: Dto.validated(model, self.body(reply, self._target), path),
            unknown=self._unknown,
            gone=self._gone,
        )

    @staticmethod
    def body(reply: Reply, target: str) -> Any:
        """The JSON of a 2xx reply; HTML or unreadable JSON is an ``UnexpectedResponseError``
        (``target``'s path, without the query, goes to its detail)."""
        path = target.split("?", 1)[0]
        if is_html(reply.headers, reply.body):
            raise UnexpectedResponseError(
                f"Serwis zwrócił stronę HTML zamiast danych. {SERVICE_CHANGED}",
                detail=f"{path}: oczekiwano JSON, przyszedł HTML",
            )
        try:
            return json.loads(reply.body)
        except (ValueError, RecursionError) as err:
            raise UnexpectedResponseError(
                f"Serwis zwrócił nieczytelne dane (niepoprawny JSON). {SERVICE_CHANGED}",
                detail=f"{path}: {err}",
            ) from err
