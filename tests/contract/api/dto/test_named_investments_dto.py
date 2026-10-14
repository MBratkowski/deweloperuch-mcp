"""Contract of ``deweloperuch_mcp.api.dto.named_investments_dto`` with the service's real
answers (the samples in docs/discovery/samples/, the raw payloads in tests/fixtures/).
"""

from deweloperuch_mcp.api.dto.named_investments_dto import NamedInvestmentsDto
from deweloperuch_mcp.models.investment_summary import InvestmentSummary
from support.providers.samples import body, envelope, untrimmed


def test_the_matches_of_a_name_sample() -> None:
    parsed = NamedInvestmentsDto.model_validate(body("api.investments_q"))

    assert [(item.name, item.slug, item.offerCount) for item in parsed.investments] == [
        ("Nowy Targówek VI", "nowy-targowek-vi", 27),
        ("Apartamenty Nowy Targ", "apartamenty-nowy-targ", 0),
    ]
    assert (parsed.hasMore, parsed.total, parsed.page) == (False, 2, 1)


def test_a_match_by_name_knows_its_active_offers_only() -> None:
    """[W] offerCount is the number of active offers (27 = active_offers of
    nowy-targowek-vi in page.investment, captured the same day)."""
    page = untrimmed(envelope("page.investment")["props"])["investments"][0]
    assert (page["slug"], page["active_offers"]) == ("nowy-targowek-vi", 27)
    dto = NamedInvestmentsDto.model_validate(body("api.investments_q")).investments[0]

    found = dto.to_model()

    assert found == InvestmentSummary(
        investment_slug="nowy-targowek-vi", name="Nowy Targówek VI", offers_active=27
    )
    assert found.ref is None  # no city, no developer: no links
