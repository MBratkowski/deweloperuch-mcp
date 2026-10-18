"""Tests of ``deweloperuch_mcp.consumers.mcp.prompts.compare_cities_prompt``."""

from deweloperuch_mcp.consumers.mcp.prompts.compare_cities_prompt import (
    MAX_CITIES,
    CompareCitiesPrompt,
)
from deweloperuch_mcp.consumers.mcp.support.prompt_base import ASK_USER
from support.providers.mcp import tools_named

PROMPT = CompareCitiesPrompt()


def test_the_prompt_is_named_for_the_client() -> None:
    assert (PROMPT.name, PROMPT.title) == ("porownaj_miasta", "Porównaj miasta")
    assert "w jednej tabeli" in PROMPT.description


def test_each_city_gets_asking_and_transaction_prices_then_one_table() -> None:
    said = PROMPT.render(miasta="Kraków, Wrocław,Gdańsk")

    assert tools_named(said) == [
        "search_locations",
        "get_market_statistics",
        "get_transaction_statistics",
        "get_government_statistics",
    ]
    assert "w miastach: Kraków, Wrocław, Gdańsk." in said
    assert "dataset=wages albo unemployment" in said
    assert "jedna tabela, wiersz na miasto" in said
    assert "list_url" in said and "stats_url" in said


def test_the_registry_lag_is_a_reminder() -> None:
    said = PROMPT.render(miasta="Kraków, Wrocław")

    assert "trafiają do RCN z opóźnieniem, więc najnowsze okresy są niepełne" in said
    assert "pomiń okresy z incomplete=true" in said
    assert "nie nowszym niż najwcześniejszy z last_complete_period wszystkich miast" in said
    assert "Miasto bez last_complete_period" in said and "oznacz jako niepewne" in said
    assert "nie traktuj jako trendu" in said


def test_at_most_five_cities_the_rest_is_named_as_skipped() -> None:
    said = PROMPT.render(miasta="A1, A2, A3, A4, A5, A6, A7")

    assert MAX_CITIES == 5
    assert "w miastach: A1, A2, A3, A4, A5." in said
    assert "Pominięte (najwyżej 5 miast naraz): A6, A7." in said


def test_empty_names_are_dropped_and_none_left_asks_the_user() -> None:
    assert "w miastach: Sopot, Gdynia." in PROMPT.render(miasta=" Sopot, , Gdynia,")
    assert f"w miastach: {ASK_USER}." in PROMPT.render(miasta=" , ")
    assert "Pominięte" not in PROMPT.render(miasta="Sopot")
