"""``SearchDevelopersTool``: developers by a part of their name."""

from typing import Annotated

from mcp.types import CallToolResult
from pydantic import Field

from deweloperuch_mcp.consumers.mcp.presenters.search_developers_mcp_presenter import (
    DevelopersResult,
    SearchDevelopersMcpPresenter,
)
from deweloperuch_mcp.consumers.mcp.support.calls import SessionContext, run, session_of
from deweloperuch_mcp.consumers.mcp.support.inputs import whole_or
from deweloperuch_mcp.consumers.mcp.support.tool_base import ToolBase
from deweloperuch_mcp.models.developer_match import DEFAULT_MATCHES, MAX_MATCHES
from deweloperuch_mcp.usecases.search_developers import SearchDevelopersRequest

Limit = Annotated[int, Field(ge=1, le=MAX_MATCHES)]


class SearchDevelopersTool(ToolBase):
    # [W] docs/discovery/endpoints.md, /api/developers: what offer_count counts is not
    # documented, hence "wg serwisu"; the profile of the whole country (city=polska) is the
    # page get_developer opens by default.
    name = "search_developers"
    title = "Szukaj deweloperów"
    description = (
        "Znajduje deweloperów (rynek pierwotny) po fragmencie nazwy, np. atal albo dom "
        "development. Użyj, żeby zamienić nazwę dewelopera na developer_slug, którego wymaga "
        "get_developer (profil dewelopera; domyślnie dla całej Polski, city=polska). Nie "
        "zwraca ofert ani cen.\n\n"
        "Zwraca items (developer_slug, name, offer_count, czyli liczbę ofert dewelopera wg "
        "serwisu, i developer_url, czyli profil na deweloperuch.pl: podawaj go użytkownikowi "
        "jako link) oraz total, returned, truncated i hint. truncated=true znaczy, że "
        "pasujących deweloperów jest więcej niż pokazano: doprecyzuj nazwę albo zwiększ limit "
        "(najwyżej 20). total jest null, gdy wiadomo tylko, że jest ich więcej."
    )

    async def __call__(
        self,
        name: Annotated[
            str,
            Field(
                title="Nazwa dewelopera",
                description="Fragment nazwy dewelopera, 2–100 znaków, np. atal, Dom Development.",
            ),
        ],
        ctx: SessionContext,
        limit: Annotated[
            Limit,
            whole_or(DEFAULT_MATCHES),
            Field(
                title="Limit wyników",
                description=(
                    "Najwięcej deweloperów w wyniku, domyślnie 5, najwyżej 20. Każdy to ok. "
                    "150 znaków wyniku."
                ),
            ),
        ] = DEFAULT_MATCHES,
    ) -> Annotated[CallToolResult, DevelopersResult]:
        session = session_of(ctx)

        def search() -> DevelopersResult:
            request = SearchDevelopersRequest.parse(name=name, limit=limit)
            return SearchDevelopersMcpPresenter().present(
                session.search_developers.execute(request)
            )

        return await run(search)
