"""Contract of ``deweloperuch_mcp.api.dto.offer_snapshot_dto`` with the service's real
answers: the raw bodies of tests/fixtures/api/ (whole) and the sample
``api.offer_snapshot.sopot`` (trimmed by the sample convention: 3 sales, each cut to its
first 3 items).
"""

import collections
import datetime as dt
import statistics

import pytest

from deweloperuch_mcp.api.dto.dto import Dto
from deweloperuch_mcp.api.dto.offer_snapshot_dto import (
    OfferSnapshotDto,
    OfferSnapshotInvestmentDto,
)
from deweloperuch_mcp.errors import UnexpectedResponseError
from deweloperuch_mcp.models.market_statistics import MarketCriteria
from deweloperuch_mcp.models.values import CitySlug
from support.providers.routes.offer_snapshot import snapshot
from support.providers.samples import body

WARSZAWA = CitySlug("warszawa")


@pytest.mark.parametrize(
    ("city", "sales", "investments"), [("sopot", 8, 2), ("warszawa", 11_672, 268)]
)
def test_the_snapshots_hold_what_the_fixture_readme_says(
    city: str, sales: int, investments: int
) -> None:
    parsed = OfferSnapshotDto.model_validate(snapshot(city))

    assert (len(parsed.sales), len(parsed.investments)) == (sales, investments)
    assert (parsed.citySlug, parsed.asOf) == (city, "2026-10-31")
    known = {item.id for item in parsed.investments}
    assert all(sale.investId in known for sale in parsed.sales)


def test_a_sale_is_read_by_its_positions() -> None:
    """[P 2026-10-31] endpoints.md section 2: ``[sale_id, invest_id, 0, amount, price per
    m², size, start difference]``; the first offer of Sopot, ``[206523, 33, 0, 3735107,
    39115.16, 95.49, 0]``."""
    parsed = OfferSnapshotDto.model_validate(snapshot("sopot"))

    first = parsed.sales[0]
    assert (first.id, first.investId, first.amount, first.size) == (206523, 33, 3735107, 95.49)
    assert (parsed.investments[0].id, parsed.investments[0].slug) == (33, "smolna")
    assert parsed.investments[0].developerSlug == "invest-komfort-spolka-akcyjna"
    assert parsed.investments[0].developer == "Invest Komfort Spółka Akcyjna Sp.K."


def test_the_offers_of_a_city_are_its_market() -> None:
    """Each offer with the slugs of its investment and developer, and the day of the data."""
    offers = OfferSnapshotDto.model_validate(snapshot("sopot")).to_model(CitySlug("sopot"))

    assert (offers.city, offers.as_of) == (CitySlug("sopot"), dt.date(2026, 10, 31))
    first = offers.offers[0]
    assert (first.offer_id, first.investment_slug, first.developer_slug) == (
        206523,
        "smolna",
        "invest-komfort-spolka-akcyjna",
    )
    assert first.developer_name == "Invest Komfort Spółka Akcyjna Sp.K."
    assert (first.price, first.area_m2, first.price_per_m2) == (3735107.0, 95.49, 39115.16)


@pytest.mark.parametrize("city", ["sopot", "warszawa"])
def test_every_investment_names_its_developer_one_name_per_developer(city: str) -> None:
    """[P 2026-10-31] ``developer`` is the developer's name on every investment, and one
    developer (``developerSlug``) has one name: the name of each top developer."""
    parsed = OfferSnapshotDto.model_validate(snapshot(city))

    names: dict[str | None, set[str | None]] = collections.defaultdict(set)
    for item in parsed.investments:
        names[item.developerSlug].add(item.developer)

    assert all(item.developer and item.developer.strip() for item in parsed.investments)
    assert all(len(found) == 1 for found in names.values())


def test_the_price_per_m2_of_the_snapshot_is_the_one_the_domain_derives() -> None:
    """[P 2026-10-31] position 4 is ``amount / size`` to 0.01 for every offer of Warszawa
    (the largest deviation 0.005), so it is not read: the summary derives it as search
    results do."""
    rows = snapshot("warszawa")["sales"]

    assert all(abs(row[3] / row[5] - row[4]) <= 0.005 + 1e-9 for row in rows)


def test_the_market_of_warszawa_from_the_real_snapshot() -> None:
    """The summary of every offer of the fixture, against the standard library."""
    data = snapshot("warszawa")
    offers = OfferSnapshotDto.model_validate(data).to_model(WARSZAWA)

    result = offers.statistics(MarketCriteria(city=WARSZAWA))

    prices = [float(row[3]) for row in data["sales"]]
    areas = [float(row[5]) for row in data["sales"]]
    assert (result.offers, result.investments, result.developers) == (11_672, 268, 100)
    for spread, values in ((result.price_spread, prices), (result.area_spread, areas)):
        quartiles = statistics.quantiles(values, n=4, method="inclusive")
        assert spread is not None
        assert (spread.min, spread.max) == (min(values), max(values))
        assert spread.p25 == pytest.approx(quartiles[0])
        assert spread.median == pytest.approx(statistics.median(values))
        assert spread.p75 == pytest.approx(quartiles[2])
    developer_of = {item["id"]: item["developerSlug"] for item in data["investments"]}
    counts = collections.Counter(developer_of[row[1]] for row in data["sales"])
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:10]
    assert [(d.developer_slug, d.offers) for d in result.top_developers] == ranked
    name_of = {item["developerSlug"]: item["developer"] for item in data["investments"]}
    assert [d.developer_name for d in result.top_developers] == [
        name_of[slug] for slug, _ in ranked
    ]
    assert result.as_of == dt.date(2026, 10, 31)


def test_the_sample_is_the_start_of_the_fixture_of_the_same_day() -> None:
    """The sample keeps both investments whole and 3 sales cut to their first 3 items."""
    sample, whole = body("api.offer_snapshot.sopot"), snapshot("sopot")

    assert (sample["citySlug"], sample["asOf"]) == (whole["citySlug"], whole["asOf"])
    assert [OfferSnapshotInvestmentDto.model_validate(item) for item in sample["investments"]] == [
        OfferSnapshotInvestmentDto.model_validate(item) for item in whole["investments"]
    ]
    assert sample["sales"] == [row[:3] for row in whole["sales"][:3]]


def test_sales_cut_short_are_a_changed_shape_not_offers() -> None:
    """The sample's rows (3 items): without the 7 positions a row cannot be read, so it
    reads as a changed service (D21), never as offers read from the wrong places."""
    with pytest.raises(UnexpectedResponseError) as caught:
        Dto.validated(OfferSnapshotDto, body("api.offer_snapshot.sopot"), "offer-snapshot")

    assert caught.value.detail is not None and "sales.0" in caught.value.detail
