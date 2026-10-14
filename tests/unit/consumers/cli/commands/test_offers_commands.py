"""Tests of ``deweloperuch_mcp.consumers.cli.commands.offers_commands``."""

import json

import respx

from deweloperuch_mcp.consumers.cli.support.common import ExitCode
from deweloperuch_mcp.flight import rsc_token
from support.builders.investments import DEVELOPER_PAGE, SMOLNA_PAGE
from support.builders.offers import offers_page
from support.providers.cli import Cli, ok
from support.providers.routes.investments import investment_routes
from support.providers.routes.offers import offers_route, unknown_city_route
from support.providers.rsc import UNKNOWN_CITY
from support.providers.samples import request_target
from support.providers.service import BASE, PAGES


def test_offers_search_prints_the_page_with_the_limits_of_d4(
    run: Cli, service: respx.MockRouter
) -> None:
    offers_route(service)  # the real Warsaw page: 10 offers

    out = ok(run("offers", "search", "warszawa"))

    lines = out.splitlines()
    assert lines[0] == (
        "Pasujące oferty: 13 324 · strona 1 z 20 (po 10) · pokazano 10 · obcięte: "
        "serwis pozwala przejrzeć najwyżej 20 stron."
    )
    assert lines[1].startswith("Wskazówka: Pasujących ofert jest 13324")
    assert (
        "[4397] D1.1.1.4 · 994 012 PLN · 55,25 m² · 17 991,17 PLN/m² · aktywna · "
        "od pierwszej ceny -5 988 PLN (-0,6%)"
    ) in lines
    assert "    Nowy Targówek VI [nowy-targowek-vi] · ATAL S.A. · Warszawa" in lines
    # Links (D12): the list as requested, then each offer's investment under it.
    assert lines[2] == f"Ta lista na deweloperuch.pl: {PAGES}/warszawa/mieszkania?page=1&perPage=10"
    where = lines.index("    Nowy Targówek VI [nowy-targowek-vi] · ATAL S.A. · Warszawa")
    assert lines[where + 1] == f"    {PAGES}/warszawa/deweloperzy/atal/nowy-targowek-vi"
    assert sum(line.startswith(f"    {PAGES}/") for line in lines) == 10
    assert lines[-1] == (
        "Szczegóły oferty: deweloperuch offers get OFFER_ID --investment INVESTMENT_SLUG"
    )


def test_offers_search_passes_every_option_to_the_service(
    run: Cli, service: respx.MockRouter
) -> None:
    """The filtered sample's request, flag by flag."""
    route = offers_route(service, offers_page("page.offers_list.filtered"))

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

    target = request_target("page.offers_list.filtered")
    assert str(route.calls.last.request.url) == f"{BASE}{target}&_rsc={rsc_token(target)}"


def test_offers_search_json_is_the_domain_model(run: Cli, service: respx.MockRouter) -> None:
    offers_route(service)

    data = json.loads(ok(run("offers", "search", "warszawa", "--json")))

    assert (data["total"], data["returned"], data["truncated"]) == (13324, 10, True)
    assert (data["page"], data["per_page"], data["pages_available"]) == (1, 10, 20)
    assert data["items"][0]["offer_id"] == 4397
    assert data["items"][0]["investment_slug"] == "nowy-targowek-vi"
    assert data["items"][0]["last_price_change_kind"] == "increase"
    assert data["list_url"] == f"{PAGES}/warszawa/mieszkania?page=1&perPage=10"
    assert (
        data["items"][0]["investment_url"] == f"{PAGES}/warszawa/deweloperzy/atal/nowy-targowek-vi"
    )


def test_offers_search_with_an_empty_page(run: Cli, service: respx.MockRouter) -> None:
    page = offers_page()
    page["data"] = []
    page["pagination"].update(total=0, totalPages=0)
    offers_route(service, page)

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
        f"Błąd: Serwis nie zna miasta {UNKNOWN_CITY!r}. Podaj city_slug z search_locations "
        "albo polska (cały kraj).",
        f"Szczegóły: /ceny-ofertowe/{UNKNOWN_CITY}/mieszkania: brak propsa 'initialData', "
        "strona zgłasza NEXT_HTTP_ERROR_FALLBACK;404",
    ]


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
