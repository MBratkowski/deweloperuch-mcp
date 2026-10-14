"""Contract of ``deweloperuch_mcp.api.dto.city_investments_dto`` with the service's real
answers (the samples in docs/discovery/samples/, the raw payloads in tests/fixtures/).
"""

import pytest
from pydantic import ValidationError

from deweloperuch_mcp.api.dto.city_investments_dto import CityInvestmentDto, CityInvestmentsDto
from deweloperuch_mcp.models.investment_summary import InvestmentSummary
from support.fakes.investment_search import KOMFORT
from support.providers.samples import body


def test_the_investments_of_a_city_sample() -> None:
    parsed = CityInvestmentsDto.model_validate(body("api.map_investments_sopot"))

    smolna, kolibki = parsed.root
    assert (smolna.slug, smolna.name, smolna.city_slug, smolna.status) == (
        "smolna",
        "Smolna",
        "sopot",
        "active",
    )
    assert (smolna.street, smolna.district) == ("Świemirowo", "")
    assert (smolna.avg_amount, smolna.avg_size, smolna.avg_price_sqm) == (
        1566392,
        63.966667,
        24522.212214,
    )
    assert (smolna.active_offers, smolna.total_offers) == (3, 16)
    assert smolna.developer.slug == "invest-komfort-spolka-akcyjna"
    assert (kolibki.slug, kolibki.street) == ("nowe-kolibki-etap-4", "")


@pytest.mark.parametrize("missing", ["slug", "name", "status", "city_slug", "developer"])
def test_a_city_investment_without_what_the_domain_needs_is_refused(missing: str) -> None:
    investment = body("api.map_investments_sopot")[0]
    del investment[missing]

    with pytest.raises(ValidationError):
        CityInvestmentsDto.model_validate([investment])


def test_numbers_may_come_as_text() -> None:
    investment = body("api.map_investments_sopot")[0]
    investment.update(avg_amount="1566392", latitude="54.42735985", avg_size="")

    found = CityInvestmentDto.model_validate(investment).to_model()

    assert (found.avg_price, found.lat, found.avg_area_m2) == (1566392.0, 54.42735985, None)


def test_a_city_investment_in_the_domains_terms() -> None:
    dto = CityInvestmentsDto.model_validate(body("api.map_investments_sopot")).root[0]

    assert dto.to_model() == InvestmentSummary(
        investment_slug="smolna",
        name="Smolna",
        status="active",
        city="Sopot",
        city_slug="sopot",
        district=None,  # "" in the sample
        street="Świemirowo",
        lat=54.42735985,
        lng=18.55839032,
        developer=KOMFORT,
        avg_price=1566392.0,
        avg_area_m2=63.97,
        avg_price_per_m2=24522.21,
        offers_active=3,
        offers_total=16,
    )


def test_the_averages_are_those_of_the_active_offers() -> None:
    """[P] the same day: smolna's averages are the means of its three active offers in
    the dump of the city's active offers (api.city_sales_sopot, its first three)."""
    smolna = body("api.map_investments_sopot")[0]
    offers = [sale for sale in body("api.city_sales_sopot")["sales"] if sale["investId"] == 33]
    assert len(offers) == smolna["active_offers"] == 3

    def mean(key: str) -> float:
        return float(sum(sale[key] for sale in offers)) / len(offers)

    assert mean("amount") == pytest.approx(smolna["avg_amount"])
    assert mean("size") == pytest.approx(smolna["avg_size"])
    # The mean of the offers' prices per m², not the total price over the total area.
    assert mean("priceSqm") == pytest.approx(smolna["avg_price_sqm"])


@pytest.mark.parametrize("value", [0, "0", "", None])
def test_an_average_of_0_is_no_average(value: object) -> None:
    """[W] a 0 means there was nothing to average: the sample's archived averages are 0
    although both investments have archived offers."""
    sample = body("api.map_investments_sopot")
    assert all(item["avg_amount_archived"] == 0 for item in sample)
    assert all(item["total_offers"] > item["active_offers"] for item in sample)
    sample[0].update(avg_amount=value, avg_size=value, avg_price_sqm=value)

    found = CityInvestmentDto.model_validate(sample[0]).to_model()

    assert (found.avg_price, found.avg_area_m2, found.avg_price_per_m2) == (None, None, None)
