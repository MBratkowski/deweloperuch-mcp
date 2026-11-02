"""Contract of ``deweloperuch_mcp.api.dto.powiat_map_stats_dto`` with the service's real
answers: the sample ``api.powiat_map_stats`` (2026-11-01) and the capture of 2026-11-02
(tests/fixtures/api/powiat_map_stats_20261102.json), with the packaged names
(``api/data/place_names.json``) from ``map/tx-cities`` of the same day.
"""

from deweloperuch_mcp.api.adapters.transaction_ranking_api import POWIAT_RANKING
from deweloperuch_mcp.api.dto.dto import Dto
from deweloperuch_mcp.api.dto.place_names_dto import PlaceNamesDto
from deweloperuch_mcp.api.dto.powiat_map_stats_dto import PowiatMapStatsDto
from deweloperuch_mcp.models.location_ranking import PRICE_ORDER_MIN_TRANSACTIONS, RankingMarket
from support.providers.routes.rankings import POWIATS_2026_11_02, TX_CITIES_2026_11_02, captured
from support.providers.samples import body


def capture() -> PowiatMapStatsDto:
    return Dto.validated(PowiatMapStatsDto, captured(POWIATS_2026_11_02), POWIAT_RANKING)


def test_380_powiats_over_12_months() -> None:
    """[P 2026-11-02], the same as the sample of 2026-11-01."""
    answer = capture()
    sample = Dto.validated(PowiatMapStatsDto, body("api.powiat_map_stats"), POWIAT_RANKING)

    assert (answer.periodStart, answer.periodEndMonth) == ("2025-11-01", "2026-10")
    assert (sample.periodStart, sample.periodEndMonth) == (answer.periodStart, "2026-10")
    assert len(answer.rows) == len({row.id for row in answer.rows}) == 380


def test_every_powiat_has_a_name_in_the_packaged_table() -> None:
    """Every id is a ``powiatId`` of ``map/tx-cities`` (380 in both) and the table holds them
    all, so no powiat is shown as ``powiat {id}``."""
    names = PlaceNamesDto.packaged().to_model()
    ids = {row.id for row in capture().rows}
    tx_ids = {row["powiatId"] for row in captured(TX_CITIES_2026_11_02)["cities"]}

    assert ids == tx_ids == set(names.powiats)


def test_missing_markets_are_null_and_no_market_has_0_transactions() -> None:
    """[P 2026-11-02]: the primary market is null in 70 powiats, the secondary in 16, both in
    3; no object has n = 0, a 0 or a null price, area or price per m²."""
    powiats = capture().to_model(PlaceNamesDto.packaged().to_model())
    objects = [
        market
        for row in capture().rows
        for market in (row.wtorny, row.pierwotny, row.oba)
        if market is not None
    ]

    assert {market: powiats.without(market) for market in RankingMarket} == {
        RankingMarket.SECONDARY: 16,
        RankingMarket.PRIMARY: 70,
        RankingMarket.ALL: 3,
    }
    assert min(market.n for market in objects) >= 1
    assert all(
        None not in (place.price_per_m2, place.area_m2, place.price)
        for market in RankingMarket
        for place in powiats.on(market)
    )


def test_the_default_threshold_leaves_out_few_powiats() -> None:
    """Behind the comment on ``PRICE_ORDER_MIN_TRANSACTIONS``: of the powiats with figures,
    31 of 364 (secondary) and 43 of 310 (primary) have fewer than 20 transactions."""
    powiats = capture().to_model(PlaceNamesDto.packaged().to_model())

    def small(market: RankingMarket) -> tuple[int, int]:
        places = powiats.on(market)
        least = PRICE_ORDER_MIN_TRANSACTIONS
        return sum(p.transaction_count < least for p in places), len(places)

    assert (small(RankingMarket.SECONDARY), small(RankingMarket.PRIMARY)) == ((31, 364), (43, 310))


def test_both_markets_are_not_the_sum_of_the_two() -> None:
    """T86 behind "nie zawsze równa się secondary + primary" in the description of market:
    of the powiats with all three markets, few have ``oba.n`` equal to the sum."""
    rows = [row for row in capture().rows if row.wtorny and row.pierwotny and row.oba]
    equal = [
        row
        for row in rows
        if row.oba and row.wtorny and row.pierwotny and row.oba.n == row.wtorny.n + row.pierwotny.n
    ]

    assert (len(equal), len(rows)) == (80, 303)
