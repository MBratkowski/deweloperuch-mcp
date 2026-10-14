"""Tests of ``deweloperuch_mcp.consumers.mcp.prompts.find_apartment_prompt``."""

from deweloperuch_mcp.consumers.mcp.prompts.find_apartment_prompt import FindApartmentPrompt
from deweloperuch_mcp.consumers.mcp.support.prompt_base import ASK_USER
from support.providers.mcp import tools_named

PROMPT = FindApartmentPrompt()


def test_the_prompt_is_named_for_the_client() -> None:
    assert (PROMPT.name, PROMPT.title) == ("znajdz_mieszkanie", "Znajdź mieszkanie")
    assert "tabela ofert od najniższej ceny za m²" in PROMPT.description


def test_the_criteria_become_filters_of_search_offers_sorted_by_price_per_m2() -> None:
    said = PROMPT.render(
        miasto="Kraków", budzet_max="800000", metraz_min="40", metraz_max="60", dzielnica="Podgórze"
    )

    assert tools_named(said) == ["search_locations", "search_offers", "get_offer"]
    assert "w mieście: Kraków." in said
    assert (
        "- dzielnica: Podgórze (district)\n"
        "- cena do: 800000 PLN (price_max)\n"
        "- metraż od: 40 m² (area_min)\n"
        "- metraż do: 60 m² (area_max)\n" in said
    )
    assert "kind=district" in said
    assert "sort=price_per_m2_asc" in said


def test_the_answer_is_a_table_with_links_and_says_rooms_are_no_filter() -> None:
    said = PROMPT.render(miasto="Gdańsk")

    assert "w tabeli" in said and "investment_url" in said and "list_url" in said
    assert "nie filtruje po liczbie pokoi ani piętrze" in said
    assert "truncated=true" in said
    assert "ceny ofertowe deweloperów, nie transakcyjne" in said


def test_without_criteria_only_the_city_narrows_the_search() -> None:
    said = PROMPT.render(miasto="Gdańsk", budzet_max="", metraz_min=" ", dzielnica=None)

    assert "Kryteria:\n- brak, poza miastem\n" in said
    assert not any(name in said for name in ("(district)", "(price_max)", "(area_min)"))
    assert "kind=district" not in said


def test_an_empty_city_asks_the_user() -> None:
    assert f"w mieście: {ASK_USER}." in PROMPT.render(miasto="")
