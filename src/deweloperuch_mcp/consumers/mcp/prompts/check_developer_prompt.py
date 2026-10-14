"""``CheckDeveloperPrompt``: a developer's investments, active offers and price changes,
in the whole country or in one city."""

from typing import Annotated

from pydantic import Field

from deweloperuch_mcp.consumers.mcp.support.prompt_base import PromptBase


class CheckDeveloperPrompt(PromptBase):
    name = "przeswietl_dewelopera"
    title = "Prześwietl dewelopera"
    description = (
        "Profil dewelopera: gdzie i ile buduje, jego inwestycje, aktywne oferty, ceny i ich "
        "zmiany; w całej Polsce albo w jednym mieście."
    )

    def render(
        self,
        nazwa: Annotated[
            str,
            Field(description="Nazwa dewelopera albo jej fragment, np. Atal, Dom Development."),
        ],
        miasto: Annotated[
            str | None,
            Field(description="Miasto, do którego zawęzić inwestycje, np. Kraków."),
        ] = None,
    ) -> str:
        developer, city = self.required(nazwa), self.given(miasto)
        steps = [
            f"search_developers(name={developer}): developer_slug. Gdy pasuje kilku, wybierz "
            "najlepiej pasującego (nazwa, liczba ofert) i wymień pozostałych; gdy nie wiadomo, "
            "o którego chodzi, zapytaj użytkownika.",
        ]
        if city:
            steps += [
                f"search_locations z nazwą miasta {city}: city_slug (kind=city).",
                "get_developer(developer_slug=developer_slug, city=city_slug): summary "
                "(aktywne oferty, średnie ceny), inwestycje z aktywnymi ofertami w tym mieście "
                "i miasta dewelopera (cities).",
                "search_investments(city=city_slug, developer_slug=developer_slug, "
                "sort=price_per_m2_asc): inwestycje dewelopera w tym mieście z ulicami i "
                "średnimi cenami za m².",
            ]
        else:
            steps += [
                "get_developer(developer_slug=developer_slug): summary (aktywne oferty, "
                "średnie ceny), inwestycje z aktywnymi ofertami i miasta dewelopera (cities).",
                "Tylko gdy użytkownik zapyta o jedno miasto z cities: search_investments("
                "city=city_slug tego miasta, developer_slug=developer_slug, "
                "sort=price_per_m2_asc).",
            ]
        steps.append(
            "Zmiany cen: dla 1–3 inwestycji z największą liczbą aktywnych ofert "
            "get_investment(investment_slug=investment_slug) z domyślnym limitem; "
            "price_change_since_start_pct ofert to obniżki (ujemne) i podwyżki od pierwszej "
            "ceny. Nie sprawdzaj wszystkich inwestycji po kolei."
        )
        plan = "\n".join(f"{number}. {step}" for number, step in enumerate(steps, start=1))
        where = f", w mieście: {city}" if city else " (cała Polska)"
        return f"""\
Prześwietl dewelopera: {developer}{where}.

Plan:
{plan}

Podsumowanie: skala (aktywne oferty, inwestycje, miasta), tabela inwestycji (nazwa, \
miasto, aktywne oferty, średnia cena za m², link investment_url), zmiany cen w \
sprawdzonych inwestycjach (ile ofert potaniało i podrożało, największe zmiany) i link \
developer_url.
Zastrzeżenie: to ceny ofertowe z deweloperuch.pl, a nie ocena kondycji finansowej ani \
rzetelności dewelopera."""
