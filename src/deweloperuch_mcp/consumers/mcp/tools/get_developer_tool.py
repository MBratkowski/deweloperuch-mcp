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
"""Investments ``get_developer`` may return: about 40k characters at most (350–400 per
investment: ATAL 330 on average, Dom Development 389, at most 474 [P 2026-10-31]); the
default 20 gives about 8.5k (a developer of 42 investments: 15.7k for all,
tests/golden/mcp/developer_*.json)."""
Limit = Annotated[int, Field(ge=1, le=MAX_DEVELOPER_LIMIT)]


class GetDeveloperTool(ToolBase):
    # [P 2026-10-31] tests/fixtures/rsc/developer_*_20261031.rsc (the 2.0 page, an internal
    # channel of the site's UI, D21): the profile lists the investments with active offers
    # (all `active`), `cities` are the same 14 on ATAL's city page and country page (a
    # developer in one city has no chart of cities: its city comes from its investments;
    # [W] that every page without the chart is such a developer, so a city's profile then
    # says in its hint that `cities` may be that city only), `summary` is summed up from
    # the investments and agrees with the page's chart of cities, and the investments'
    # figures match the offer snapshot of the same day
    # (tests/contract/api/dto/test_developer_page_dto.py). The page names no website. A
    # known developer in a city without its offers, and an unknown city, are [H] (T39).
    name = "get_developer"
    title = "Profil dewelopera"
    description = """\
Zwraca profil dewelopera: nazwę, podsumowanie jego aktywnych ofert (summary), inwestycje \
z aktywnymi ofertami (najpierw te z największą liczbą aktywnych ofert) i jego miasta \
(cities, od miasta z największą liczbą aktywnych ofert). Nie podaje strony www \
dewelopera. Użyj, gdy pytanie dotyczy dewelopera: gdzie i ile buduje, w jakich cenach. \
developer_slug weź z search_developers (po nazwie) albo z pól developer_slug w \
search_offers, get_investment, get_offer i get_market_statistics (top_developers). \
developer_url i investment_url to strony na deweloperuch.pl: podawaj je użytkownikowi jako \
linki.

city zawęża summary i investments do jednego miasta (city_slug z search_locations albo z \
cities); domyślnie polska (cała Polska). cities obejmuje całą Polskę (gdy serwis nie \
podaje listy miast, tylko miasta inwestycji: wtedy hint). summary liczy narzędzie z \
inwestycji w zakresie city; summary.cities to liczba miast. Średnia cena oferty w jednym \
mieście: city=<city_slug>, pole summary.avg_price.

Ograniczenia: najwyżej limit inwestycji (domyślnie 20); o pominięciu mówią \
investments_omitted (ile), truncated i hint. Pojedynczych ofert tu nie ma: oferty \
inwestycji daje get_investment."""

    async def __call__(
        self,
        developer_slug: Annotated[
            str,
            Field(
                title="Deweloper",
                description=(
                    "developer_slug z search_developers (po nazwie) albo z pól developer_slug w "
                    "search_offers, get_investment, get_offer, get_market_statistics "
                    "(top_developers), np. atal."
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
                    "city_slug miasta z search_locations albo z cities wyniku get_developer "
                    "(np. krakow), albo polska (domyślnie: cała Polska)."
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
                    "ofert), 1–100, domyślnie 20. Inwestycja to 350–400 znaków wyniku; zwykle "
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
