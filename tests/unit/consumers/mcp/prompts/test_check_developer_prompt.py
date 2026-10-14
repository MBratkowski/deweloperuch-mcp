"""Tests of ``deweloperuch_mcp.consumers.mcp.prompts.check_developer_prompt``."""

from deweloperuch_mcp.consumers.mcp.prompts.check_developer_prompt import CheckDeveloperPrompt
from deweloperuch_mcp.consumers.mcp.support.prompt_base import ASK_USER
from support.providers.mcp import tools_named

PROMPT = CheckDeveloperPrompt()


def test_the_prompt_is_named_for_the_client() -> None:
    assert (PROMPT.name, PROMPT.title) == ("przeswietl_dewelopera", "Prześwietl dewelopera")
    assert "gdzie i ile buduje" in PROMPT.description


def test_in_a_city_the_profile_and_the_investments_there() -> None:
    said = PROMPT.render(nazwa="Atal", miasto="Kraków")

    assert tools_named(said) == [
        "search_developers",
        "search_locations",
        "get_developer",
        "search_investments",
        "get_investment",
    ]
    assert "Prześwietl dewelopera: Atal, w mieście: Kraków." in said
    assert "search_developers(name=Atal)" in said
    assert "get_developer(developer_slug=developer_slug, city=city_slug)" in said
    assert "search_investments(city=city_slug, developer_slug=developer_slug" in said
    assert "\n5. " in said and "\n6. " not in said


def test_without_a_city_the_whole_country_and_no_investment_search() -> None:
    said = PROMPT.render(nazwa="Dom Development", miasto="")

    assert tools_named(said) == [
        "search_developers",
        "get_developer",
        "search_investments",
        "get_investment",
    ]
    assert "Prześwietl dewelopera: Dom Development (cała Polska)." in said
    assert "get_developer(developer_slug=developer_slug)" in said
    assert "Tylko gdy użytkownik zapyta o jedno miasto z cities: search_investments(" in said
    assert "\n4. " in said and "\n5. " not in said


def test_the_summary_has_links_price_changes_and_its_limits() -> None:
    said = PROMPT.render(nazwa="Atal")

    assert "price_change_since_start_pct" in said
    assert "investment_url" in said and "developer_url" in said
    assert "nie ocena kondycji finansowej ani rzetelności dewelopera" in said


def test_an_empty_name_asks_the_user() -> None:
    assert f"Prześwietl dewelopera: {ASK_USER}" in PROMPT.render(nazwa="\t")
