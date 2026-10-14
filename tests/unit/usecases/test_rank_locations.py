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
from support.fakes.rankings import FakeRankingLinks, FakeRankingSource, city


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
