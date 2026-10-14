"""``FindApartmentPrompt``: offers in one city within a budget, an area and a district,
cheapest per m² first, as a table with links."""

from typing import Annotated

from pydantic import Field

from deweloperuch_mcp.consumers.mcp.support.prompt_base import PromptBase


class FindApartmentPrompt(PromptBase):
    name = "znajdz_mieszkanie"
    title = "Znajdź mieszkanie"
    description = (
        "Mieszkania od deweloperów w jednym mieście z budżetem, metrażem i dzielnicą: "
        "tabela ofert od najniższej ceny za m² z linkami do deweloperuch.pl."
    )

    def render(
        self,
        miasto: Annotated[str, Field(description="Miasto, np. Kraków, Gdańsk.")],
        budzet_max: Annotated[
            str | None, Field(description="Najwyższa cena mieszkania w PLN, np. 800000.")
        ] = None,
        metraz_min: Annotated[
            str | None, Field(description="Najmniejszy metraż w m², np. 40.")
        ] = None,
        metraz_max: Annotated[
            str | None, Field(description="Największy metraż w m², np. 65.")
        ] = None,
        dzielnica: Annotated[str | None, Field(description="Dzielnica, np. Mokotów.")] = None,
    ) -> str:
        district = self.given(dzielnica)
        criteria = "\n".join(
            line.format(value)
            for line, value in (
                ("- dzielnica: {} (district)", district),
                ("- cena do: {} PLN (price_max)", self.given(budzet_max)),
                ("- metraż od: {} m² (area_min)", self.given(metraz_min)),
                ("- metraż do: {} m² (area_max)", self.given(metraz_max)),
            )
            if value is not None
        )
        district_step = (
            " Dzielnicę też znajdź przez search_locations: jej nazwę (kind=district, pole "
            "name) przekaż jako district razem z city_slug jej miasta."
            if district
            else ""
        )
        return f"""\
Znajdź mieszkania od deweloperów (rynek pierwotny) w mieście: {self.required(miasto)}.
Kryteria:
{criteria or "- brak, poza miastem"}

Plan:
1. search_locations z nazwą miasta: weź city_slug miasta (kind=city, offer_count większe \
od 0).{district_step}
2. search_offers z city=city_slug, filtrami z kryteriów (nazwa parametru w nawiasie) i \
sort=price_per_m2_asc (od najniższej ceny za m²), per_page=10. Kwoty i metraże podaj jako \
liczby całkowite (np. 800 tys. zł to 800000).
3. Pokaż wynik w tabeli: inwestycja, deweloper, cena, metraż, cena za m², zmiana ceny od \
pierwszej i link investment_url. Pod tabelą podaj total (ile ofert pasuje) i list_url \
(ta lista na deweloperuch.pl).

Uwagi:
- search_offers nie filtruje po liczbie pokoi ani piętrze (serwis nie ma takich danych): \
gdy użytkownikowi chodzi o pokoje, powiedz to i zawęź metraż.
- Gdy truncated=true, zaproponuj węższe kryteria zamiast przeglądać kolejne strony.
- To ceny ofertowe deweloperów, nie transakcyjne. Historię ceny jednej oferty daje \
get_offer."""
