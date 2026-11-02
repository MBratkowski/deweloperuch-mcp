"""Contract of ``deweloperuch_mcp.api.dto.city_lookup_dto`` with the service's real answers
(the samples in docs/discovery/samples/, the raw payload in tests/fixtures/api/)."""

import json

import pytest

from deweloperuch_mcp.api.dto.city_lookup_dto import CityLookupDto
from deweloperuch_mcp.models.place import Place
from support.providers.routes.city_lookup import UNKNOWN_SLUG_LOOKUP
from support.providers.samples import body, request_target


def test_a_village_of_the_transactions_dictionary_is_a_place() -> None:
    """[P 2026-11-01] sample api.city_lookup.village_transactions: the register's name."""
    assert request_target("api.city_lookup.village_transactions").endswith(
        "slug=ignatki-osiedle&source=transactions"
    )
    found = CityLookupDto.model_validate(body("api.city_lookup.village_transactions"))

    assert found.to_model() == Place(name="Ignatki-osiedle", slug="ignatki-osiedle")


def test_a_slug_the_service_does_not_know_is_no_place() -> None:
    """[P 2026-11-02] tests/fixtures/api/city_lookup_unknown_slug_20261102.json: an unknown
    slug with ``source=transactions`` is a 200 with both fields null, as an unknown name is
    (sample api.city_lookup.unknown, [P 2026-11-01])."""
    found = CityLookupDto.model_validate(json.loads(UNKNOWN_SLUG_LOOKUP.read_bytes()))

    assert found.to_model() is None


@pytest.mark.parametrize(
    ("sample", "expected"),
    [
        ("api.city_lookup.unknown", None),
        ("api.city_lookup.slug_transactions", Place(name="Kraków", slug="krakow")),
    ],
)
def test_the_other_samples_read_the_same_way(sample: str, expected: Place | None) -> None:
    assert CityLookupDto.model_validate(body(sample)).to_model() == expected


def test_the_transactions_dictionary_holds_the_offers_places_the_samples_show() -> None:
    """[W] ``CityLookupApi``: the transactions dictionary is taken for a superset of the
    offers one. The two samples of ``krak`` (offers 2026-10-09, transactions 2026-10-30,
    both trimmed) show Kraków and Krakowiany in both, with the same slugs and names; the
    offers sample's third place (Krakulice) is in the trimmed part of the other."""
    offers = {row["city_slug"]: row["city"] for row in body("api.cities_q")["cityMappings"]}
    transactions = {
        row["city_slug"]: row["city"] for row in body("api.cities_q.transactions")["cityMappings"]
    }

    shown_in_both = {slug: transactions[slug] for slug in offers.keys() & transactions.keys()}

    assert shown_in_both == {"krakow": "Kraków", "krakowiany": "Krakowiany"}
    assert all(offers[slug] == name for slug, name in shown_in_both.items())
