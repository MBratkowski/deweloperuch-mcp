"""``AssessOfferPrompt``: one offer's price against its history, its city's market and a
valuation from nearby transactions, with a verdict and its caveats."""

from typing import Annotated

from pydantic import Field

from deweloperuch_mcp.consumers.mcp.support.prompt_base import PromptBase


class AssessOfferPrompt(PromptBase):
    # The investment page's address ends with the investment's slug: the [P] route
    # /ceny-ofertowe/{city}/deweloperzy/{developerSlug}/{investmentSlug}
    # (docs/discovery/pages-rsc.md; ``api/links.py``).
    name = "ocen_oferte"
    title = "Oceń ofertę"
    description = (
        "Ocena ceny jednej oferty: historia ceny (najniższa z 30 i 90 dni, podejrzane "
        "obniżki), porównanie z rynkiem miasta i z wyceną z transakcji w okolicy; werdykt "
        "z zastrzeżeniami."
    )

    def render(
        self,
        offer_id: Annotated[
            str, Field(description="offer_id oferty z wyników search_offers albo get_investment.")
        ],
        investment_slug: Annotated[
            str,
            Field(
                description=(
                    "investment_slug inwestycji tej oferty, np. smolna: z tych samych wyników "
                    "albo ostatni człon adresu strony inwestycji na deweloperuch.pl."
                )
            ),
        ],
    ) -> str:
        offer, investment = self.required(offer_id), self.required(investment_slug)
        return f"""\
Oceń ofertę mieszkania: offer_id {offer}, inwestycja {investment}. Czy cena jest rozsądna?

Plan:
1. get_offer(offer_id={offer}, investment_slug={investment}): cena, metraż, cena za m², \
status, historia ceny i price_flags. Porównaj obecną cenę z lowest_price_30d i \
lowest_price_90d (najniższą ceną z 30 i 90 dni), sprawdź liczbę zmian (price_changes), \
największą obniżkę i podwyżkę (largest_drop_pct, largest_rise_pct) i suspicious_reduction \
(obniżka do 30 dni po podwyżce, „promocja” po podwyżce).
2. get_market_statistics(city=city_slug z get_offer): gdzie wypada cena za m² oferty na \
tle p25, mediany i p75 miasta. Dla podobnych mieszkań zawęź area_min i area_max wokół \
metrażu oferty (np. ±10 m²).
3. get_investment(investment_slug={investment}, limit=0): współrzędne lat i lng \
inwestycji. Gdy są, estimate_property_value(lat, lng, area_m2=metraż oferty, limit=5): \
wycena z transakcji w okolicy. Bez współrzędnych pomiń wycenę i powiedz o tym.

Werdykt: krótko (np. okazja, w normie albo drogo na tle rynku) z liczbami: cena za m² \
oferty, mediana miasta, wycena z transakcji; do tego wnioski z historii ceny i linki \
investment_url i developer_url.

Zastrzeżenia, które podaj użytkownikowi:
- get_offer i get_market_statistics to ceny ofertowe (ile chce deweloper), a \
estimate_property_value to ceny transakcyjne z Rejestru Cen Nieruchomości (za ile \
sprzedano, z kilkumiesięcznym opóźnieniem); to różne miary, nie licz z nich jednej średniej.
- Wycena jest przybliżona: to porównanie z transakcjami w pobliżu, nie operat szacunkowy.
- Gdy estimate_property_value zwróci low_confidence=true (mniej niż 5 transakcji \
porównawczych), przekaż zastrzeżenie z pola hint: wycena jest wtedy tylko orientacyjna.
- Statystyki miasta obejmują tylko aktywne oferty; przy ofercie wycofanej \
(status=archived) porównujesz jej ostatnią cenę z dzisiejszym rynkiem."""
