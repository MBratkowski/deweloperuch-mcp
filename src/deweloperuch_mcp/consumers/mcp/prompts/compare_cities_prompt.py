"""``CompareCitiesPrompt``: a few cities side by side, asking prices of developers next to
transaction prices of the price register, in one table."""

from typing import Annotated

from pydantic import Field

from deweloperuch_mcp.consumers.mcp.support.prompt_base import ASK_USER, PromptBase

MAX_CITIES = 5
"""Cities compared at once: each costs a few requests to the service (D2)."""


class CompareCitiesPrompt(PromptBase):
    name = "porownaj_miasta"
    title = "Porównaj miasta"
    description = (
        "Porównanie rynku mieszkań kilku miast: ceny ofertowe deweloperów, ceny "
        "transakcyjne z RCN i opcjonalnie wynagrodzenia i bezrobocie z GUS, w jednej tabeli."
    )

    def render(
        self,
        miasta: Annotated[
            str,
            Field(
                description=(
                    "Nazwy miast rozdzielone przecinkami, np. Kraków, Wrocław, Gdańsk "
                    f"(najwyżej {MAX_CITIES})."
                )
            ),
        ],
    ) -> str:
        cities = [name for part in miasta.split(",") if (name := self.given(part))]
        compared, skipped = cities[:MAX_CITIES], cities[MAX_CITIES:]
        skipped_note = (
            f"\nPominięte (najwyżej {MAX_CITIES} miast naraz): {', '.join(skipped)}. "
            "Zaproponuj je użytkownikowi w kolejnym porównaniu."
            if skipped
            else ""
        )
        return f"""\
Porównaj rynek mieszkań w miastach: {", ".join(compared) or ASK_USER}.{skipped_note}

Dla każdego miasta:
1. search_locations z nazwą miasta: city_slug (kind=city).
2. get_market_statistics(city=city_slug): ceny ofertowe deweloperów: mediana ceny za m² \
(z p25 i p75), mediana ceny i metrażu, liczba ofert, inwestycji i deweloperów.
3. get_transaction_statistics(city=city_slug): ceny transakcyjne z Rejestru Cen \
Nieruchomości (RCN): mediana ceny za m² i liczba transakcji w kolejnych miesiącach.
4. Gdy rozmowa dotyczy dostępności mieszkań albo rynku pracy: \
get_government_statistics(location=nazwa miasta małymi literami bez polskich znaków, z \
myślnikami zamiast spacji, np. krakow, bielsko-biala; dataset=wages albo unemployment). \
Nie wymaga search_locations; dane są tylko dla miast na prawach powiatu.

Wynik: jedna tabela, wiersz na miasto: mediana ceny ofertowej za m², liczba ofert, cena \
transakcyjna za m² z okresem, którego dotyczy, liczba transakcji (i wynagrodzenie albo \
bezrobocie, jeśli je pobrano). Pod tabelą krótkie wnioski i linki list_url i stats_url. \
Gdy dla miasta brak danych, wpisz „brak” zamiast zgadywać.

Pamiętaj:
- Ceny ofertowe (ile chcą deweloperzy) i transakcyjne (za ile sprzedano) to różne miary: \
pokazuj je w osobnych kolumnach.
- Transakcje trafiają do RCN z opóźnieniem, więc najnowsze okresy są niepełne: pomiń \
okresy z incomplete=true i porównuj miasta na tym samym okresie, nie nowszym niż \
najwcześniejszy z last_complete_period wszystkich miast. Miasto bez last_complete_period \
(za mało transakcji, przeczytaj hint) oznacz jako niepewne zamiast porównywać; spadku w \
ostatnich miesiącach nie traktuj jako trendu."""
