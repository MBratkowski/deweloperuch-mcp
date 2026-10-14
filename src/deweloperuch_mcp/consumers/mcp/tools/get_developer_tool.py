"""``GetDeveloperTool``: a developer's profile with its investments and cities."""

from typing import Annotated

from mcp.types import CallToolResult
from pydantic import Field

from deweloperuch_mcp.consumers.mcp.presenters.get_developer_mcp_presenter import (
    DeveloperResult,
    GetDeveloperMcpPresenter,
)
from deweloperuch_mcp.consumers.mcp.support.calls import SessionContext, run, session_of
from deweloperuch_mcp.consumers.mcp.support.inputs import null_is, whole_or
from deweloperuch_mcp.consumers.mcp.support.tool_base import ToolBase
from deweloperuch_mcp.models.developer_profile import DEFAULT_INVESTMENTS_LIMIT
from deweloperuch_mcp.models.values import WHOLE_COUNTRY
from deweloperuch_mcp.usecases.get_developer import GetDeveloperRequest

MAX_DEVELOPER_LIMIT = 100
"""Investments ``get_developer`` may return: about 38k characters at most; the default 20
gives about 9.5k (a developer of 42 investments: 17k for all, [P 2026-10-13])."""
Limit = Annotated[int, Field(ge=1, le=MAX_DEVELOPER_LIMIT)]


class GetDeveloperTool(ToolBase):
    # [P 2026-10-13] tests/fixtures/rsc/developer_atal_*.rsc: the profile lists the
    # investments with active offers (all `active`, every one with active offers; the
    # developer has more investments by name), `cities` are the same 14 on the city's and
    # the country's page, and the figures of `summary` and `cities` match the page's own
    # offers (tests/contract/api/dto/test_developer_page_dto.py). An unknown city with a
    # known developer is [H].
    name = "get_developer"
    title = "Profil dewelopera"
    description = """\
Zwraca profil dewelopera: nazwę, stronę www, podsumowanie jego aktywnych ofert (summary: \
active_offers, cities, avg_price, avg_area_m2, avg_price_per_m2), inwestycje z \
aktywnymi ofertami (najpierw te z największą liczbą aktywnych ofert: investment_slug, \
name, city, active_offers, total_offers razem z archiwalnymi, średnie aktywnych ofert, \
investment_url) i jego miasta (cities: inwestycje, aktywne oferty, średnia cena i cena \
za m²). Użyj, gdy pytanie dotyczy dewelopera: gdzie i ile buduje, w jakich cenach. \
developer_slug weź z search_developers (po nazwie) albo z pól developer_slug w \
search_offers, get_investment, get_offer. developer_url i investment_url to strony na \
deweloperuch.pl: podawaj je użytkownikowi jako linki.

city zawęża summary i investments do jednego miasta (city_slug z search_locations); \
domyślnie polska (cała Polska). cities zawsze obejmuje całą Polskę.

Ograniczenia: najwyżej limit inwestycji (domyślnie 20); investments_omitted i truncated \
mówią, ile pominięto. Pojedynczych ofert tu nie ma: oferty inwestycji daje \
get_investment."""

    async def __call__(
        self,
        developer_slug: Annotated[
            str,
            Field(
                title="Deweloper",
                description=(
                    "developer_slug z search_developers (po nazwie) albo z pól developer_slug w "
                    "search_offers, get_investment, get_offer, np. atal."
                ),
            ),
        ],
        ctx: SessionContext,
        city: Annotated[
            str,
            null_is(WHOLE_COUNTRY),
            Field(
                title="Miasto",
                description=(
                    "city_slug miasta z search_locations (np. krakow) albo polska (domyślnie: "
                    "cała Polska)."
                ),
            ),
        ] = WHOLE_COUNTRY,
        limit: Annotated[
            Limit,
            whole_or(DEFAULT_INVESTMENTS_LIMIT),
            Field(
                title="Limit inwestycji",
                description=(
                    "Najwięcej inwestycji w wyniku (najpierw te z największą liczbą aktywnych "
                    "ofert), 1–100, domyślnie 20. Inwestycja to ok. 350 znaków wyniku; zwykle "
                    "wystarcza domyślne 20."
                ),
            ),
        ] = DEFAULT_INVESTMENTS_LIMIT,
    ) -> Annotated[CallToolResult, DeveloperResult]:
        session = session_of(ctx)

        def get() -> DeveloperResult:
            request = GetDeveloperRequest.parse(
                developer_slug=developer_slug, city=city, limit=limit
            )
            presenter = GetDeveloperMcpPresenter(max_limit=MAX_DEVELOPER_LIMIT)
            return presenter.present(session.get_developer.execute(request))

        return await run(get)
