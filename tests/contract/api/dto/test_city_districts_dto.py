"""Contract of ``deweloperuch_mcp.api.dto.city_districts_dto`` with the service's real answers
(the sample in docs/discovery/samples/, the raw payloads in tests/fixtures/api/)."""

import pytest
from pydantic import ValidationError

from deweloperuch_mcp.api.dto.city_districts_dto import CityDistrictsDto
from support.builders.districts import WARSZAWA_DISTRICTS_20261102
from support.paths import API_FIXTURES
from support.providers.samples import body, envelope


def test_the_offers_districts_of_warszawa() -> None:
    """[P 2026-11-01] 18 districts ``{name, slug, count}``, sorted by ``count``; the capture of
    2026-11-02 has the same 18 in the same order."""
    parsed = CityDistrictsDto.model_validate_json(WARSZAWA_DISTRICTS_20261102.read_bytes())

    assert len(parsed.districts) == 18
    assert [(row.name, row.slug) for row in parsed.districts[:3]] == [
        ("Białołęka", "bialoleka"),
        ("Praga-Północ", "praga-polnoc"),
        ("Mokotów", "mokotow"),
    ]
    assert (parsed.districts[-1].name, parsed.districts[-1].slug) == ("Żoliborz", "zoliborz")


def test_the_sample_agrees_with_the_capture() -> None:
    parsed = CityDistrictsDto.model_validate(body("api.city_districts.offers_v2"))
    captured = CityDistrictsDto.model_validate_json(WARSZAWA_DISTRICTS_20261102.read_bytes())

    assert parsed.districts == captured.districts[:3]


@pytest.mark.parametrize(
    "fixture",
    ["city_districts_warszawa_tx_20261031.json", "city_districts_krakow_tx_20261031.json"],
)
def test_the_transactions_variant_has_the_same_shape(fixture: str) -> None:
    """[P 2026-10-30] the same ``{name, slug, count}`` rows (not requested by the client, which
    asks for the offers' districts only)."""
    parsed = CityDistrictsDto.model_validate_json((API_FIXTURES / fixture).read_bytes())

    assert len(parsed.districts) == 18


def test_the_trimmed_sample_is_refused() -> None:
    with pytest.raises(ValidationError):
        CityDistrictsDto.model_validate(envelope("api.city_districts.offers_v2")["response"])
