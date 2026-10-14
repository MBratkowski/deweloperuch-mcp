"""Contract of ``deweloperuch_mcp.api.dto.location_search_dto`` with the service's real
answers (the samples in docs/discovery/samples/, the raw payloads in tests/fixtures/).
"""

from deweloperuch_mcp.api.dto.location_search_dto import LocationSearchDto
from support.providers.samples import body


def test_location_search_sample() -> None:
    parsed = LocationSearchDto.model_validate(body("api.location_search"))

    district, street = parsed.suggestions
    assert (district.kind, district.city, district.citySlug) == ("district", "Warszawa", "warszawa")
    assert (district.district, district.street, district.count) == ("Mokotów", None, 1562)
    assert district.lat == 52.189818153819054
    assert district.lng == 21.05171136865118
    assert (street.kind, street.street, street.district, street.count) == (
        "street",
        "Mokotów",
        "Mokotów",
        191,
    )
