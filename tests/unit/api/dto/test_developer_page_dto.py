"""Tests of ``deweloperuch_mcp.api.dto.developer_page_dto``: the shapes the real pages of
2026-10-31 do not show (counts that are no counts, a missing tip, renamed keys, zeros, a
chart moved or renamed, other elements with the developer's props) and the pages without
the data. The contract with the real pages is in
tests/contract/api/dto/test_developer_page_dto.py.
"""

import logging
from typing import Any

import pytest
from pydantic import ValidationError

from deweloperuch_mcp.api.dto.developer_page_dto import (
    CITIES_CHART,
    DeveloperCityRowDto,
    DeveloperInvestmentDto,
    DeveloperPageDto,
)
from deweloperuch_mcp.errors import SERVICE_CHANGED, NotFoundError, UnexpectedResponseError
from deweloperuch_mcp.flight import NOT_FOUND_DIGEST, component_props
from deweloperuch_mcp.models.developer_profile import DeveloperCity
from deweloperuch_mcp.models.offer import DeveloperRef
from deweloperuch_mcp.models.values import CitySlug, InvestmentsLimit
from deweloperuch_mcp.usecases.get_developer import GetDeveloperResult
from support.providers.routes.developer_profiles import without_cities_chart
from support.providers.rsc import (
    DEVELOPER_UNKNOWN_20261031,
    DEVELOPER_WARSZAWA_20261031,
    raw,
    replace_prop,
    swap_props,
)
from support.providers.samples import body

PATH = "/ceny-ofertowe/warszawa/deweloperzy/atal"
ROW: dict[str, Any] = body("page.developer.v2_spec")["views"][""]["rows"][0]
"""The real row of Warsaw in the chart of cities: 4 investments, ``"60"`` active offers."""
LOGGER = "deweloperuch_mcp.api.dto.developer_page_dto"
INVESTMENT_KEYS = (
    "name",
    "slug",
    "status",
    "city",
    "city_slug",
    "active_offers",
    "total_offers",
    "avg_amount",
    "avg_size",
    "avg_price_sqm",
)
"""The keys of an investment the DTO reads, each required."""


def city(**changes: Any) -> DeveloperCity:
    """The real row of Warsaw with ``changes``."""
    return DeveloperCityRowDto.model_validate({**ROW, **changes}).to_model()


def chart(value: Any, chart_id: str) -> bool:
    return isinstance(value, dict) and value.get("id") == chart_id


def parsed(payload: bytes) -> DeveloperPageDto:
    return DeveloperPageDto.from_payload(payload, path=PATH)


def test_a_city_reads_its_counts_from_their_display_text() -> None:
    assert city() == DeveloperCity(
        city="Warszawa",
        city_slug="warszawa",
        investments=4,
        active_offers=60,
        avg_price_per_m2=16110.0,
    )


@pytest.mark.parametrize(
    ("extra", "count"),
    [
        ("1\u00a0816", 1816),
        ("1\u202f816", 1816),
        ("1 816", 1816),
        (" 60 ", 60),
        (60, 60),
        (60.0, 60),
        (0, 0),
        ("0", 0),
        ("", None),
        ("60 ofert", None),
        ("6,5", None),
        ("-5", None),
        ("٦٠", None),
        (6.5, None),
        (-5, None),
        (None, None),
    ],
)
def test_a_count_is_its_digits_grouped_or_not(extra: Any, count: int | None) -> None:
    """[P 2026-10-31] the page groups the thousands of a count with a no-break space
    (Dom Development in Warsaw: ``"1 816"``, tests/fixtures/rsc/
    developer_dom_development_warszawa_20261031.rsc); a plain or narrow no-break space is
    read too. Anything else is no count (``None``), not an error."""
    assert city(extra=extra).active_offers == count


def test_a_flag_is_no_count_but_a_changed_chart() -> None:
    with pytest.raises(ValidationError):
        city(extra=True)


def test_a_count_left_out_is_logged_unless_its_text_is_empty(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger=LOGGER)

    city(extra="60 ofert")
    city(extra="")
    city(extra=None)

    warned = [record for record in caplog.records if record.name == LOGGER]
    assert [record.levelno for record in warned] == [logging.WARNING]
    assert "'60 ofert'" in warned[0].getMessage()


def test_the_log_shows_at_most_80_characters_of_the_services_text(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger=LOGGER)

    city(extra="x" * 300)

    (record,) = [record for record in caplog.records if record.name == LOGGER]
    assert "x" * 80 + "…" in record.getMessage()
    assert "x" * 81 not in record.getMessage()


def test_a_city_without_its_tip_has_no_count_of_investments() -> None:
    without_investments = [row for row in ROW["tip"]["rows"] if row["key"] != "inwestycje"]

    assert city(tip=None).investments is None
    assert city(tip={"rows": without_investments}).investments is None
    assert city(tip=None).active_offers == 60  # the column ``extra`` is no tip


def test_a_row_of_the_tip_without_its_value_is_refused() -> None:
    """A renamed ``value`` must not turn the count of investments into ``None``."""
    with pytest.raises(ValidationError):
        city(tip={"rows": [{"key": "inwestycje", "label": "Inwestycje"}]})


@pytest.mark.parametrize("key", ["extra", "tip", "value", "label"])
def test_a_row_of_the_chart_without_a_key_it_reads_is_refused(key: str) -> None:
    """A renamed key must not turn every count into ``None``: the keys are required, their
    values may be null."""
    with pytest.raises(ValidationError):
        DeveloperCityRowDto.model_validate({k: v for k, v in ROW.items() if k != key})


def test_a_zero_average_is_no_average() -> None:
    """The service writes 0 where it has no value [P 2026-10-20 on the 1.0 page, live:
    ``atal`` in ``bialystok``]: 0 is no price (``Dto._positive``)."""
    rows = next(
        value
        for name, value in component_props(raw(DEVELOPER_WARSZAWA_20261031))
        if name == "investments" and isinstance(value, list)
    )
    zeros = {**rows[0], "avg_amount": 0, "avg_size": 0, "avg_price_sqm": 0}

    investment = DeveloperInvestmentDto.model_validate(zeros).to_model(
        DeveloperRef(developer_slug="atal", name="ATAL S.A.")
    )

    assert (investment.avg_price, investment.avg_area_m2, investment.avg_price_per_m2) == (
        None,
        None,
        None,
    )
    assert city(value=0).avg_price_per_m2 is None


@pytest.mark.parametrize("key", INVESTMENT_KEYS)
def test_an_investment_without_a_key_it_reads_is_a_changed_service(key: str) -> None:
    """The real page with ``key`` dropped from its first investment."""
    page = raw(DEVELOPER_WARSZAWA_20261031)
    rows = next(
        value
        for name, value in component_props(page)
        if name == "investments" and isinstance(value, list)
    )
    changed = [{k: v for k, v in rows[0].items() if k != key}, *rows[1:]]
    payload = replace_prop(page, "investments", lambda value: value == rows, changed)

    with pytest.raises(UnexpectedResponseError, match=SERVICE_CHANGED) as caught:
        parsed(payload)

    assert caught.value.detail is not None and key in caught.value.detail


def test_the_page_of_an_unknown_developer_is_not_found() -> None:
    """[P 2026-10-31] a 200 without the developer, with Next.js's 404 marker (1.0 showed a
    heading „Deweloper nie znaleziony” instead, without the marker)."""
    with pytest.raises(NotFoundError) as caught:
        parsed(raw(DEVELOPER_UNKNOWN_20261031))

    assert caught.value.detail is not None and NOT_FOUND_DIGEST in caught.value.detail


def test_a_page_without_the_developer_nor_the_404_marker_is_a_changed_service() -> None:
    payload = raw(DEVELOPER_UNKNOWN_20261031).replace(
        NOT_FOUND_DIGEST.encode(), b"NEXT_HTTP_ERROR_FALLBACK;500"
    )

    with pytest.raises(UnexpectedResponseError, match=SERVICE_CHANGED) as caught:
        parsed(payload)

    assert caught.value.detail is not None and "developerName" in caught.value.detail


def test_a_page_whose_developer_props_were_renamed_is_a_changed_service() -> None:
    payload = raw(DEVELOPER_WARSZAWA_20261031).replace(b'"developerName":', b'"developerTitle":')

    with pytest.raises(UnexpectedResponseError, match=SERVICE_CHANGED) as caught:
        parsed(payload)

    assert caught.value.detail is not None and "developerName" in caught.value.detail


def test_a_page_without_the_chart_of_cities_takes_the_cities_of_its_investments() -> None:
    """[W] a page without the chart is a developer in one city
    (tests/fixtures/rsc/developer_ceres_warszawa_20261031.rsc [P 2026-10-31]); here the
    real page of ATAL in Warsaw with the chart renamed: its one city (of 14), from its
    investments, and a hint that the developer may build elsewhere too."""
    profile = parsed(without_cities_chart(raw(DEVELOPER_WARSZAWA_20261031))).to_model(
        CitySlug("warszawa")
    )
    listing = profile.listing(InvestmentsLimit(20))
    result = GetDeveloperResult(
        listing=listing, developer_url=None, investment_urls=(None,) * len(listing.investments)
    )

    assert profile.cities == (
        DeveloperCity(
            city="Warszawa",
            city_slug="warszawa",
            investments=4,
            active_offers=60,
            avg_price_per_m2=16110.0,
        ),
    )
    assert (profile.cities_from_investments, profile.cities_in_scope_only) == (True, True)
    assert result.hint == (
        "Serwis nie podał listy miast dewelopera: cities to tylko miasta inwestycji w city "
        "(wszystkie: city=polska)."
    )


def test_a_page_with_the_chart_of_cities_takes_the_services_list() -> None:
    profile = parsed(raw(DEVELOPER_WARSZAWA_20261031)).to_model(CitySlug("warszawa"))

    assert (len(profile.cities), profile.cities_from_investments) == (14, False)


def test_a_chart_of_cities_of_another_shape_is_a_changed_service() -> None:
    payload = raw(DEVELOPER_WARSZAWA_20261031).replace(b'"views":{"":{', b'"views":{"x":{', 1)

    with pytest.raises(UnexpectedResponseError, match=SERVICE_CHANGED):
        parsed(payload)


def test_the_chart_of_cities_is_found_by_its_id_wherever_it_is() -> None:
    """Here it is the second of the four charts."""
    payload = swap_props(
        raw(DEVELOPER_WARSZAWA_20261031),
        "spec",
        lambda value: chart(value, CITIES_CHART),
        lambda value: chart(value, "rozklad-metrazy"),
    )
    first = next(value for name, value in component_props(payload) if name == "spec")

    found = parsed(payload)

    assert first["id"] == "rozklad-metrazy"
    assert found.cities is not None and len(found.cities.views.default.rows) == 14


def test_another_elements_developer_props_do_not_count() -> None:
    """Only the ``hero`` element's props are read. The page has a second ``developerSlug``,
    in another element (with ``cleanedName``) [P 2026-10-31]: here it differs, and an element
    before the hero holds a reference, ``$undefined`` and null under the hero's names (a test
    of the shape: one row put in front of the real page)."""
    page = raw(DEVELOPER_WARSZAWA_20261031)
    head, _, tail = page.rpartition(b'"developerSlug":"atal"')
    other = head + b'"developerSlug":"inny-deweloper"' + tail
    row = (
        b'0:["$","$L1",null,{"investments":"$2:props:investments",'
        b'"developerName":"$undefined","developerSlug":null}]\n'
    )
    slugs = [value for name, value in component_props(other) if name == "developerSlug"]

    found = parsed(row + other)

    assert slugs == ["atal", "inny-deweloper"]
    assert (found.developerSlug, found.developerName) == ("atal", "ATAL S.A.")
    assert len(found.investments) == 4
