"""``SearchDevelopersMcpPresenter``: ``search_developers``' result for a model, and its output
schema (``DevelopersResult``)."""

from pydantic import Field

from deweloperuch_mcp.consumers.mcp.support.mcp_model import DEVELOPER_URL, McpModel
from deweloperuch_mcp.consumers.shared.developer_views import DeveloperSearchView
from deweloperuch_mcp.usecases.search_developers import SearchDevelopersResult

# [W] docs/discovery/endpoints.md, /api/developers: what offerCount counts is not
# documented (api.developer_search), hence "wg serwisu".
DEVELOPER_OFFER_COUNT = "Liczba ofert dewelopera wg serwisu."

# Class docstrings would become schema descriptions for the model: comments instead.


class DeveloperItem(McpModel):
    developer_slug: str = Field(description="Identyfikator dewelopera dla get_developer.")
    name: str
    offer_count: int | None = Field(None, description=DEVELOPER_OFFER_COUNT)
    developer_url: str | None = Field(None, description=DEVELOPER_URL)


class DevelopersResult(McpModel):
    keep_null = frozenset({"total"})  # D4: always there, null when unknown

    total: int | None = Field(
        description="Wszyscy pasujący deweloperzy; null, gdy wiadomo tylko, że jest ich więcej."
    )
    returned: int
    truncated: bool = Field(
        description="true: pasujących deweloperów jest więcej niż pokazano; co dalej, mówi hint."
    )
    hint: str | None = None
    items: list[DeveloperItem]


class SearchDevelopersMcpPresenter:
    """The developers as their view has them (``DeveloperSearchView``); ``dump`` leaves out
    ``null``, except ``total``."""

    def present(self, result: SearchDevelopersResult) -> DevelopersResult:
        return DevelopersResult.model_validate(DeveloperSearchView.from_result(result).model_dump())
