"""Tests of ``deweloperuch_mcp.consumers.mcp.prompts.assess_offer_prompt``."""

from deweloperuch_mcp.consumers.mcp.prompts.assess_offer_prompt import AssessOfferPrompt
from deweloperuch_mcp.consumers.mcp.support.prompt_base import ASK_USER
from support.providers.mcp import tools_named

PROMPT = AssessOfferPrompt()


def test_the_prompt_is_named_for_the_client() -> None:
    assert (PROMPT.name, PROMPT.title) == ("ocen_oferte", "Oceń ofertę")
    assert "werdykt z zastrzeżeniami" in PROMPT.description


def test_the_offer_then_the_city_then_a_valuation_at_the_investment() -> None:
    said = PROMPT.render(offer_id="2377", investment_slug="smolna")

    assert tools_named(said) == [
        "get_offer",
        "get_market_statistics",
        "get_investment",
        "estimate_property_value",
    ]
    assert "get_offer(offer_id=2377, investment_slug=smolna)" in said
    assert "get_investment(investment_slug=smolna, limit=0)" in said


def test_the_price_flags_are_read() -> None:
    said = PROMPT.render(offer_id="2377", investment_slug="smolna")

    for flag in ("lowest_price_30d", "lowest_price_90d", "price_changes", "suspicious_reduction"):
        assert flag in said


def test_the_verdict_keeps_asking_and_transaction_prices_apart() -> None:
    said = PROMPT.render(offer_id="2377", investment_slug="smolna")

    assert "Werdykt:" in said
    assert "ceny ofertowe (ile chce deweloper)" in said
    assert "ceny transakcyjne z Rejestru Cen Nieruchomości" in said
    assert "nie operat szacunkowy" in said
    assert "Bez współrzędnych pomiń wycenę" in said
    assert "status=archived" in said


def test_empty_arguments_ask_the_user() -> None:
    said = PROMPT.render(offer_id=" ", investment_slug="")

    assert f"offer_id {ASK_USER}, inwestycja {ASK_USER}" in said
