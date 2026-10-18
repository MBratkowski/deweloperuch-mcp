"""Tests of ``deweloperuch_mcp.usecases.rank_locations``."""

import pytest

from deweloperuch_mcp.models.errors import (
    InvalidInputError,
    InvalidValueError,
    NotFoundError,
    ServiceBlockedError,
    ServiceError,
    UnexpectedResponseError,
)
from deweloperuch_mcp.models.location_ranking import (
    RANKING_LIMIT_MAX,
    LocationRanking,
    LocationTransactions,
    MinTransactions,
    RankingCriteria,
    RankingLevel,
    RankingOrder,
)
from deweloperuch_mcp.usecases import ports
from deweloperuch_mcp.usecases.rank_locations import (
    RankLocations,
    RankLocationsRequest,
    RankLocationsResult,
)
from support.builders.rankings import criteria, names
from support.fakes.rankings import (
    KRAKOW,
    NO_PRICE,
    VILLAGE,
    WARSZAWA,
    WROCLAW,
    FakeRankingLinks,
    FakeRankingSource,
    city,
)


def rank(source: ports.TransactionRankingSource, given: RankingCriteria) -> RankLocationsResult:
    links: ports.RankingLinks = FakeRankingLinks()
    return RankLocations(source, links).execute(RankLocationsRequest(criteria=given))


def ranking_hint(ranking: LocationRanking) -> str | None:
    return RankLocationsResult(ranking=ranking, ranking_url=None).hint


def test_one_question_per_ranking_and_the_link_of_the_cities_ranking() -> None:
    source = FakeRankingSource()

    found = rank(source, criteria(limit=2))

    assert source.asked == [RankingLevel.CITY]
    assert names(found.ranking) == ["Warszawa", "Kraków"]
    assert found.ranking_url == "<ranking miast>"
    assert found.hint == (
        "Pokazano pierwsze 2 z 5 miejscowości; kolejne pokaże większy limit (najwyżej 100)."
    )


def test_powiats_have_no_ranking_page() -> None:
    powiat = LocationTransactions(
        name="powiat Sopot", powiat_id=208, transaction_count=10, price_per_m2=None
    )
    source = FakeRankingSource({RankingLevel.CITY: (), RankingLevel.POWIAT: (powiat,)})

    found = rank(source, criteria(level=RankingLevel.POWIAT))

    assert source.asked == [RankingLevel.POWIAT]
    assert found.ranking.items == (powiat,)
    assert found.ranking_url is None
    assert found.hint is None


@pytest.mark.parametrize(
    ("given", "hint"),
    [
        (criteria(limit=5), None),
        (criteria(limit=100), None),
        (
            criteria(min_transactions=10_000),
            "Żadne miejsce nie ma co najmniej 10000 transakcji: zmniejsz min_transactions.",
        ),
    ],
)
def test_hints_say_what_to_change(given: RankingCriteria, hint: str | None) -> None:
    assert rank(FakeRankingSource(), given).hint == hint


def test_at_the_largest_limit_the_hint_points_to_min_transactions() -> None:
    many = tuple(city(f"M{index:03}", index + 1) for index in range(150))
    ranking = LocationRanking.of(criteria(limit=RANKING_LIMIT_MAX), many)

    assert ranking_hint(ranking) == (
        "Pokazano pierwsze 100 z 150 miejscowości; to najwięcej w jednym wywołaniu. Pomiń "
        "małe miejsca przez min_transactions albo zmień sort."
    )
    powiats = LocationRanking.of(criteria(limit=3, level=RankingLevel.POWIAT), many)
    assert ranking_hint(powiats) == (
        "Pokazano pierwsze 3 z 150 powiatów; kolejne pokaże większy limit (najwyżej 100)."
    )


LEFT_OUT = (
    "Przy sortowaniu po cenie pominięto miejsca z mniej niż 20 transakcjami (domyślny próg); "
    "wszystkie miejsca pokaże min_transactions=0."
)
"""The hint's word on the price orders' default threshold."""


@pytest.mark.parametrize(
    ("given", "ranked", "hint"),
    [
        (
            criteria(RankingOrder.PRICE_PER_M2_ASC, min_transactions=None),
            ["Wrocław", "Kraków", "Warszawa"],
            LEFT_OUT,
        ),
        (
            criteria(RankingOrder.PRICE_PER_M2_DESC, limit=2, min_transactions=None),
            ["Warszawa", "Kraków"],
            f"{LEFT_OUT} Pokazano pierwsze 2 z 3 miejscowości; kolejne pokaże większy limit "
            "(najwyżej 100).",
        ),
    ],
)
def test_by_price_the_hint_says_small_places_were_left_out_by_default(
    given: RankingCriteria, ranked: list[str], hint: str
) -> None:
    """Wieś (1 transaction, the highest price) and Bez ceny (2) are left out."""
    found = rank(FakeRankingSource(), given)

    assert names(found.ranking) == ranked
    assert found.ranking.criteria.threshold == MinTransactions(20)
    assert found.hint == hint


def test_the_default_threshold_with_the_other_hints() -> None:
    many = tuple(city(f"M{index:03}", index + 1) for index in range(150))
    at_most = LocationRanking.of(
        criteria(RankingOrder.PRICE_PER_M2_ASC, RANKING_LIMIT_MAX, None), many
    )
    small = FakeRankingSource({RankingLevel.CITY: (VILLAGE, NO_PRICE), RankingLevel.POWIAT: ()})

    assert ranking_hint(at_most) == (
        f"{LEFT_OUT} Pokazano pierwsze 100 z 131 miejscowości; to najwięcej w jednym "
        "wywołaniu. Pomiń małe miejsca przez min_transactions albo zmień sort."
    )
    assert rank(small, criteria(RankingOrder.PRICE_PER_M2_ASC, min_transactions=None)).hint == (
        f"{LEFT_OUT} Żadne miejsce nie ma co najmniej 20 transakcji: zmniejsz min_transactions."
    )


def test_no_word_on_the_default_when_it_left_no_place_out() -> None:
    """Every place has at least 20 transactions: the default threshold changes nothing."""
    big = (WARSZAWA, KRAKOW, WROCLAW)
    source = FakeRankingSource({RankingLevel.CITY: big, RankingLevel.POWIAT: ()})

    found = rank(source, criteria(RankingOrder.PRICE_PER_M2_DESC, min_transactions=None))

    assert found.ranking.criteria.threshold_by_default is True
    assert (found.ranking.total, found.ranking.left_out) == (3, 0)
    assert found.hint is None


@pytest.mark.parametrize(
    "given",
    [
        criteria(RankingOrder.PRICE_PER_M2_ASC, min_transactions=20),
        criteria(RankingOrder.PRICE_PER_M2_DESC, min_transactions=0),
        criteria(RankingOrder.TRANSACTIONS_DESC, min_transactions=None),
    ],
)
def test_no_word_on_the_default_when_min_transactions_was_given_or_none_applies(
    given: RankingCriteria,
) -> None:
    assert rank(FakeRankingSource(), given).hint is None


@pytest.mark.parametrize(
    ("level", "subject"),
    [(RankingLevel.CITY, "Ranking miejscowości"), (RankingLevel.POWIAT, "Ranking powiatów")],
)
@pytest.mark.parametrize(
    ("error", "kind"),
    [
        (ServiceError("Serwis nie odpowiada; spróbuj później.", 10.0), ServiceError),
        (UnexpectedResponseError("Inny format."), UnexpectedResponseError),
        (NotFoundError("Brak danych."), NotFoundError),
    ],
)
def test_a_failure_of_the_source_says_which_ranking_failed(
    level: RankingLevel, subject: str, error: Exception, kind: type[Exception]
) -> None:
    with pytest.raises(kind) as caught:
        rank(FakeRankingSource(error=error), criteria(level=level))

    assert type(caught.value) is kind
    assert str(caught.value).startswith(f"{subject}: ")


def test_a_stop_passes_unchanged() -> None:
    stop = ServiceBlockedError("STOP: odmowa dostępu.")

    with pytest.raises(ServiceBlockedError) as caught:
        rank(FakeRankingSource(error=stop), criteria())

    assert caught.value is stop


def test_the_arguments_default_to_the_ranking_of_cities_by_transactions() -> None:
    assert RankLocationsRequest.parse().criteria == RankingCriteria()
    assert RankLocationsRequest.parse(
        level="powiat", sort="price_per_m2_asc", limit=5, min_transactions=50
    ).criteria == criteria(RankingOrder.PRICE_PER_M2_ASC, 5, 50, RankingLevel.POWIAT)


@pytest.mark.parametrize(
    ("sort", "min_transactions", "given", "threshold"),
    [
        ("price_per_m2_asc", None, None, 20),
        ("price_per_m2_desc", None, None, 20),
        ("transactions_desc", None, None, 0),
        ("price_per_m2_asc", 0, 0, 0),
        ("price_per_m2_desc", 5, 5, 5),
    ],
)
def test_min_transactions_not_given_leaves_the_threshold_to_the_order(
    sort: str, min_transactions: int | None, given: int | None, threshold: int
) -> None:
    found = RankLocationsRequest.parse(sort=sort, min_transactions=min_transactions).criteria

    assert found.min_transactions == (None if given is None else MinTransactions(given))
    assert found.threshold == MinTransactions(threshold)


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (
            {"level": "gmina"},
            "level musi być jedną z wartości city, powiat, podano 'gmina'.",
        ),
        (
            {"sort": "price_desc"},
            "sort musi być jedną z wartości transactions_desc, price_per_m2_desc, "
            "price_per_m2_asc, podano 'price_desc'.",
        ),
        (
            {"limit": 0},
            "limit musi być liczbą całkowitą z zakresu 1–100 (liczba pozycji rankingu), podano 0.",
        ),
        (
            {"min_transactions": -1},
            "min_transactions musi być liczbą całkowitą z zakresu 0–10000000 (najmniejsza "
            "liczba transakcji miejsca w rankingu), podano -1.",
        ),
    ],
)
def test_wrong_arguments_say_which_parameter_to_fix(
    arguments: dict[str, object], message: str
) -> None:
    with pytest.raises(InvalidInputError) as caught:
        RankLocationsRequest.parse(**arguments)

    assert str(caught.value) == message
    assert not isinstance(caught.value, InvalidValueError)
