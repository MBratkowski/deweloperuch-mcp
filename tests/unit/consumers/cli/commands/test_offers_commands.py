"""Tests of ``deweloperuch_mcp.consumers.cli.commands.offers_commands``."""

import json

import respx

from deweloperuch_mcp.consumers.cli.support.common import ExitCode
from support.builders.investments import DEVELOPER_PAGE, SMOLNA_PAGE
from support.builders.offers import WHOLE_COUNTRY_MESSAGE, offers_page
from support.providers.cli import Cli, ok
from support.providers.routes.city_lookup import UNKNOWN_PLACE_MESSAGE
from support.providers.routes.investments import investment_routes
from support.providers.routes.offers import offers_route, unknown_city_route
from support.providers.rsc import UNKNOWN_CITY
from support.providers.service import BASE, PAGES

BEETHOVENA = f"{PAGES}/warszawa/deweloperzy/dom-development/apartamenty-beethovena"


def test_offers_search_prints_the_page_with_the_limits_of_d4(
    run: Cli, service: respx.MockRouter
) -> None:
    offers_route(service)  # the real Warsaw page, its first 10 offers

    out = ok(run("offers", "search", "warszawa"))

    lines = out.splitlines()
    assert lines[0] == (
        "Pasujące oferty: 11 672 · strona 1 z 20 (po 10) · pokazano 10 · obcięte: "
        "serwis pozwala przejrzeć najwyżej 20 stron."
    )
    assert lines[1].startswith("Wskazówka: Pasujących ofert jest 11672")
    assert lines[3] == (
        "[4487] A2 · 810 660 PLN · 35,4 m² · 22 900 PLN/m² · aktywna · "
        "od pierwszej ceny +660 PLN (+0,08%)"
    )
    # Links (D12): the list as requested, then each offer's investment under it.
    assert lines[2] == f"Ta lista na deweloperuch.pl: {PAGES}/warszawa/mieszkania?perPage=10"
    assert lines[4:6] == [
        "    Apartamenty Beethovena [apartamenty-beethovena] · Dom Development S.A. · Warszawa",
        f"    {BEETHOVENA}",
    ]
    assert sum(line.startswith(f"    {PAGES}/") for line in lines) == 10
    assert lines[-1] == (
        "Szczegóły oferty: deweloperuch offers get OFFER_ID --investment INVESTMENT_SLUG"
    )


def test_offers_search_passes_every_option_to_the_service(
    run: Cli, service: respx.MockRouter
) -> None:
    """Every option, flag by flag, as the request's parameters (pages-rsc.md)."""
    route = offers_route(service, offers_page(total=1192, page=2, per_page=50))

    ok(
        run(
            "offers",
            "search",
            "warszawa",
            "--price-min",
            "500000",
            "--price-max",
            "700000",
            "--area-min",
            "40",
            "--area-max",
            "60",
            "--sort",
            "price_asc",
            "--page",
            "2",
            "--per-page",
            "50",
        )
    )

    target = (
        "/ceny-ofertowe/warszawa/mieszkania?filterPrice=500000-700000&filterSize=40-60"
        "&sortBy=amount&sortOrder=asc&page=2&perPage=50"
    )
    assert str(route.calls.last.request.url) == f"{BASE}{target}&_rsc="


def test_offers_search_json_is_the_domain_model(run: Cli, service: respx.MockRouter) -> None:
    offers_route(service)

    data = json.loads(ok(run("offers", "search", "warszawa", "--json")))

    assert (data["total"], data["returned"], data["truncated"]) == (11672, 10, True)
    assert (data["page"], data["per_page"], data["pages_available"]) == (1, 10, 20)
    assert data["items"][0]["offer_id"] == 4487
    assert data["items"][0]["investment_slug"] == "apartamenty-beethovena"
    assert (data["items"][0]["city"], data["items"][0]["city_slug"]) == ("Warszawa", "warszawa")
    assert data["items"][0]["district"] == "Mokotów"
    assert data["items"][0]["last_price_change_kind"] == "increase"
    assert data["list_url"] == f"{PAGES}/warszawa/mieszkania?perPage=10"
    assert data["items"][0]["investment_url"] == BEETHOVENA


def test_offers_search_with_an_empty_page(run: Cli, service: respx.MockRouter) -> None:
    offers_route(service, offers_page(total=0))

    out = ok(run("offers", "search", "warszawa"))

    assert out.splitlines()[0] == "Pasujące oferty: 0 · pokazano 0."
    assert "Wskazówka: Brak ofert spełniających kryteria." in out
    assert "offers get" not in out


def test_offers_search_of_an_unknown_city_ends_with_not_found(
    run: Cli, service: respx.MockRouter
) -> None:
    """The real answer for an unknown city (HTTP 200 with Next.js's 404 marker): code 7,
    the domain message, the details on their own line; nothing on stdout."""
    unknown_city_route(service)

    result = run("offers", "search", UNKNOWN_CITY)

    assert result.exit_code == 7  # ExitCode.NOT_FOUND, public API
    assert result.stdout == ""
    assert result.stderr.splitlines() == [
        f"Błąd: {UNKNOWN_PLACE_MESSAGE}",
        f"Szczegóły: /ceny-ofertowe/{UNKNOWN_CITY}/mieszkania: brak propsów 'sales', "
        "'serverPaginationData', strona zgłasza NEXT_HTTP_ERROR_FALLBACK;404",
    ]


def test_offers_search_of_the_whole_country_is_invalid_input(
    run: Cli, service: respx.MockRouter
) -> None:
    """[P 2026-10-29] the service's list of Poland is a list of cities: code 2, nothing
    sent."""
    result = run("offers", "search", "polska", "--district", "Mokotów")

    assert result.exit_code == 2  # ExitCode.INVALID_INPUT, public API
    assert result.stdout == ""
    assert result.stderr.splitlines() == [f"Błąd: {WHOLE_COUNTRY_MESSAGE}"]
    assert service.calls.call_count == 0


def test_offers_search_in_a_district_asks_for_the_district_list(
    run: Cli, service: respx.MockRouter
) -> None:
    """[P 2026-10-31] the district's own list, at its slug; the link is that list."""
    route = offers_route(service)

    out = ok(run("offers", "search", "warszawa", "--district", "Praga-Południe"))

    assert route.calls.last.request.url.path == "/ceny-ofertowe/warszawa/praga-poludnie/mieszkania"
    assert (
        f"Ta lista na deweloperuch.pl: {PAGES}/warszawa/praga-poludnie/mieszkania?perPage=10"
        in out.splitlines()
    )


def test_offers_get_prints_the_offer_with_its_price_history(
    run: Cli, service: respx.MockRouter
) -> None:
    investment_routes(service)

    out = ok(run("offers", "get", "2377", "--investment", "smolna"))

    assert out.splitlines() == [
        "[2377] C224 · aktywna",
        "Cena: 1 620 175 PLN · 69,5 m² · 23 311,87 PLN/m²",
        "Od pierwszej ceny: +175 PLN (+0,01%)",
        "Inwestycja: Smolna [smolna] · Sopot",
        f"Strona inwestycji: {SMOLNA_PAGE}",
        "Deweloper: Invest Komfort Spółka Akcyjna Sp.K. [invest-komfort-spolka-akcyjna]",
        f"Profil dewelopera: {DEVELOPER_PAGE}",
        "Daty: dodana 2025-02-25 · ostatnie zdarzenie 2026-10-03 · ostatnia zmiana 2026-10-03",
        # Flags: withdrawn since 2025-02-25, back at 1 620 175 on 2026-10-03; the same
        # for every day since then.
        "Najniższa cena: z 30 dni 1 620 175 PLN · z 90 dni 1 620 175 PLN",
        "Zmiany ceny: 1 · największa obniżka brak · największa podwyżka 0,01%",
        "Podejrzana obniżka: nie",
        "Historia ceny (3):",
        "  2025-02-25  cena          1 620 000 PLN",
        "  2025-02-25  wycofanie     1 620 000 PLN",
        "  2026-10-03  przywrócenie  1 620 175 PLN",
    ]


def test_offers_get_json_is_the_domain_model(run: Cli, service: respx.MockRouter) -> None:
    investment_routes(service)

    data = json.loads(ok(run("offers", "get", "2377", "--investment", "smolna", "--json")))

    assert (data["offer_id"], data["investment_slug"], data["price"]) == (2377, "smolna", 1620175.0)
    assert data["developer"]["developer_slug"] == "invest-komfort-spolka-akcyjna"
    assert [event["kind"] for event in data["price_history"]] == ["offer", "archived", "restored"]


def test_offers_get_requires_the_investment(run: Cli, service: respx.MockRouter) -> None:
    result = run("offers", "get", "2377")

    assert result.exit_code == ExitCode.INVALID_INPUT
    assert "--investment" in result.stderr
    assert run.sessions == []
    assert service.calls.call_count == 0
