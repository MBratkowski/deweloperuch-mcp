"""Tests of ``deweloperuch_mcp.usecases.rank_locations``."""

import dataclasses

import pytest

from deweloperuch_mcp.models.errors import (
    InvalidInputError,
    InvalidValueError,
    NotFoundError,
    ServiceBlockedError,
    ServiceError,
    UnexpectedResponseError,
)
from deweloperuch_mcp.models.indicator_ranking import (
    Indicator,
    IndicatorCriteria,
    IndicatorValues,
)
from deweloperuch_mcp.models.location_ranking import (
    RANKING_LIMIT_MAX,
    LocationRanking,
    LocationTransactions,
    MinTransactions,
    PowiatTransactions,
    RankingCriteria,
    RankingLevel,
    RankingLimit,
    RankingMarket,
    RankingOrder,
    TransactionPeriod,
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
    UNEMPLOYMENT,
    VILLAGE,
    WARSZAWA,
    WROCLAW,
    FakeIndicatorSource,
    FakeRankingLinks,
    FakeRankingSource,
    city,
)


def rank(
    source: ports.TransactionRankingSource,
    given: RankingCriteria | IndicatorCriteria,
    indicators: ports.CityIndicatorSource | None = None,
) -> RankLocationsResult:
    links: ports.RankingLinks = FakeRankingLinks()
    return RankLocations(source, indicators or FakeIndicatorSource(), links).execute(
        RankLocationsRequest(criteria=given)
    )


def ranking_hint(ranking: LocationRanking) -> str | None:
    return RankLocationsResult(ranking=ranking, ranking_url=None).hint


def transactions(found: RankLocationsResult) -> LocationRanking:
    assert isinstance(found.ranking, LocationRanking)
    return found.ranking


def test_one_question_per_ranking_and_the_link_of_the_cities_ranking() -> None:
    source = FakeRankingSource()

    found = rank(source, criteria(limit=2))

    assert source.asked == ["cities"]
    assert names(transactions(found)) == ["Warszawa", "Kraków"]
    assert found.ranking_url == "<ranking miast>"
    assert found.period is None
    assert found.hint == (
        "Pokazano pierwsze 2 z 5 miejscowości; kolejne pokaże większy limit (najwyżej 100)."
    )


def test_powiats_have_no_ranking_page_and_name_their_period() -> None:
    powiat = LocationTransactions(
        name="powiat Sopot", powiat_id=208, transaction_count=10, price_per_m2=None
    )
    period = TransactionPeriod(start="2025-11-01", end="2026-10")
    source = FakeRankingSource(
        powiats_are=PowiatTransactions(
            period=period, powiats=1, markets={RankingMarket.SECONDARY: (powiat,)}
        )
    )

    found = rank(source, criteria(level=RankingLevel.POWIAT))

    assert source.asked == ["powiats"]
    assert found.ranking.items == (powiat,)
    assert (found.ranking_url, found.period, found.hint) == (None, period, None)


ALL_THREE = ["powiat Warszawa", "powiat Kraków", "powiat Sopot"]


@pytest.mark.parametrize(
    ("market", "ranked", "hint"),
    [
        (None, ALL_THREE, None),
        (RankingMarket.SECONDARY, ALL_THREE, None),
        (
            RankingMarket.PRIMARY,
            ["powiat Warszawa", "powiat Kraków"],
            "Pominięto powiaty, dla których serwis nie podaje danych rynku pierwotnego "
            "(market=primary): 1.",
        ),
        (RankingMarket.ALL, ALL_THREE, None),
    ],
)
def test_powiat_ranking_leaves_out_powiats_without_the_market(
    market: RankingMarket | None, ranked: list[str], hint: str | None
) -> None:
    """Sopot has no primary market [P 2026-11-02]: left out and counted, never shown with 0."""
    found = rank(FakeRankingSource(), criteria(level=RankingLevel.POWIAT, market=market))

    assert names(transactions(found)) == ranked
    assert found.without_data == (1 if market is RankingMarket.PRIMARY else 0)
    assert found.hint == hint
    assert 0 not in [item.transaction_count for item in transactions(found).items]


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

    assert names(transactions(found)) == ranked
    assert transactions(found).criteria.threshold == MinTransactions(20)
    assert found.hint == hint


def test_the_default_threshold_with_the_other_hints() -> None:
    many = tuple(city(f"M{index:03}", index + 1) for index in range(150))
    at_most = LocationRanking.of(
        criteria(RankingOrder.PRICE_PER_M2_ASC, RANKING_LIMIT_MAX, None), many
    )
    small = FakeRankingSource(cities_are=(VILLAGE, NO_PRICE))

    assert ranking_hint(at_most) == (
        f"{LEFT_OUT} Pokazano pierwsze 100 z 131 miejscowości; to najwięcej w jednym "
        "wywołaniu. Pomiń małe miejsca przez min_transactions albo zmień sort."
    )
    assert rank(small, criteria(RankingOrder.PRICE_PER_M2_ASC, min_transactions=None)).hint == (
        f"{LEFT_OUT} Żadne miejsce nie ma co najmniej 20 transakcji: zmniejsz min_transactions."
    )


def test_no_word_on_the_default_when_it_left_no_place_out() -> None:
    """Every place has at least 20 transactions: the default threshold changes nothing."""
    source = FakeRankingSource(cities_are=(WARSZAWA, KRAKOW, WROCLAW))

    found = rank(source, criteria(RankingOrder.PRICE_PER_M2_DESC, min_transactions=None))

    assert transactions(found).criteria.threshold_by_default is True
    assert (transactions(found).total, transactions(found).left_out) == (3, 0)
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
    ("given", "subject"),
    [
        (criteria(), "Ranking miejscowości"),
        (criteria(level=RankingLevel.POWIAT), "Ranking powiatów"),
        (IndicatorCriteria(Indicator.UNEMPLOYMENT_RATE), "Ranking miast według wskaźnika"),
    ],
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
    given: RankingCriteria | IndicatorCriteria,
    subject: str,
    error: Exception,
    kind: type[Exception],
) -> None:
    with pytest.raises(kind) as caught:
        rank(FakeRankingSource(error=error), given, FakeIndicatorSource(error=error))

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
        level="powiat", sort="price_per_m2_asc", limit=5, min_transactions=50, market="primary"
    ).criteria == criteria(
        RankingOrder.PRICE_PER_M2_ASC, 5, 50, RankingLevel.POWIAT, RankingMarket.PRIMARY
    )
    powiats = RankLocationsRequest.parse(level="powiat").criteria
    assert powiats == criteria(min_transactions=None, level=RankingLevel.POWIAT)
    assert isinstance(powiats, RankingCriteria)
    assert powiats.powiat_market is RankingMarket.SECONDARY


@pytest.mark.parametrize(
    ("sort", "min_transactions", "given", "threshold"),
    [
        ("price_per_m2_asc", None, None, 20),
        ("price_per_m2_desc", None, None, 20),
        ("transactions_desc", None, None, 0),
        (None, None, None, 0),
        ("price_per_m2_asc", 0, 0, 0),
        ("price_per_m2_desc", 5, 5, 5),
    ],
)
def test_min_transactions_not_given_leaves_the_threshold_to_the_order(
    sort: str | None, min_transactions: int | None, given: int | None, threshold: int
) -> None:
    found = RankLocationsRequest.parse(sort=sort, min_transactions=min_transactions).criteria

    assert isinstance(found, RankingCriteria)
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
            "price_per_m2_asc, value_desc, value_asc, podano 'price_desc'.",
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
        (
            {"level": "powiat", "market": "wtorny"},
            "market musi być jedną z wartości secondary, primary, all, podano 'wtorny'.",
        ),
        (
            {"indicator": "bezrobocie"},
            "indicator musi być jedną z wartości unemployment_rate, average_wage, "
            "dwellings_completed, dwellings_started, average_dwelling_area, natural_increase, "
            "nbp_price_per_m2, podano 'bezrobocie'.",
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


# --- what the parameters need of each other ------------------------------------------------------


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        pytest.param(
            {"market": "primary"},
            "market działa tylko z level=powiat: ranking miejscowości nie dzieli transakcji "
            "na rynki; pomiń market albo podaj level=powiat.",
            id="market_is_refused_at_city_level",
        ),
        pytest.param(
            {"sort": "value_desc"},
            "sort value_desc i value_asc działa tylko z indicator; podaj indicator albo sort "
            "transactions_desc, price_per_m2_desc lub price_per_m2_asc.",
            id="value_sorts_need_an_indicator",
        ),
        pytest.param(
            {"level": "powiat", "indicator": "average_wage"},
            "indicator działa tylko z level=city: wskaźniki GUS/NBP są tylko dla 66 miast na "
            "prawach powiatu, a dla powiatów są tylko transakcje (market). Pomiń level, aby "
            "dostać ranking miast według wskaźnika, albo pomiń indicator, aby dostać ranking "
            "powiatów według transakcji.",
            id="indicator_refuses_powiats",
        ),
        pytest.param(
            {"indicator": "average_wage", "min_transactions": 0},
            "min_transactions nie działa z indicator: ranking wskaźnika nie liczy transakcji; "
            "pomiń min_transactions.",
            id="indicator_refuses_min_transactions",
        ),
        pytest.param(
            {"indicator": "average_wage", "market": "all"},
            "market nie działa z indicator: rynek dotyczy transakcji powiatów; pomiń market.",
            id="indicator_refuses_market",
        ),
        pytest.param(
            {"indicator": "average_wage", "sort": "price_per_m2_desc"},
            "Z indicator sort przyjmuje value_desc (najwyższa wartość, domyślnie) albo "
            "value_asc (najniższa); pomiń sort albo podaj jedną z nich.",
            id="transaction_sorts_are_refused_with_an_indicator",
        ),
    ],
)
def test_parameters_that_do_not_go_together_are_refused(
    arguments: dict[str, object], message: str
) -> None:
    """The refusal names what to change (D12); nothing is sent."""
    with pytest.raises(InvalidInputError) as caught:
        RankLocationsRequest.parse(**arguments)

    assert str(caught.value) == message


@pytest.mark.parametrize(
    ("arguments", "order"),
    [
        ({"indicator": "average_wage"}, RankingOrder.VALUE_DESC),
        ({"indicator": "average_wage", "level": "city"}, RankingOrder.VALUE_DESC),
        ({"indicator": " average_wage ", "sort": "value_asc"}, RankingOrder.VALUE_ASC),
    ],
)
def test_an_indicator_ranks_by_its_value(arguments: dict[str, object], order: RankingOrder) -> None:
    found = RankLocationsRequest.parse(limit=7, **arguments).criteria

    assert found == IndicatorCriteria(Indicator.AVERAGE_WAGE, order, RankingLimit(7))


# --- rankings by an indicator --------------------------------------------------------------------


def test_indicator_ranking_leaves_out_cities_without_it() -> None:
    """NBP prices for 17 of the 66 cities of 2026-11-02: 17 items, 49 counted in the hint,
    each city linked to its page of government statistics."""
    indicators = FakeIndicatorSource()
    source = FakeRankingSource()

    found = rank(
        source, IndicatorCriteria(Indicator.NBP_PRICE_PER_M2, limit=RankingLimit(100)), indicators
    )

    assert (indicators.asked, source.asked) == ([Indicator.NBP_PRICE_PER_M2], [])
    assert (found.ranking.total, found.ranking.returned, found.without_data) == (17, 17, 49)
    assert found.hint == "Pominięto miasta, dla których serwis nie podaje tego wskaźnika: 49 z 66."
    assert len(found.stats_urls) == 17
    assert found.stats_urls[0] == "<dane rządowe warszawa#None>"
    assert found.ranking_url is None


def test_a_cut_indicator_ranking_says_how_to_see_more() -> None:
    found = rank(
        FakeRankingSource(), IndicatorCriteria(Indicator.UNEMPLOYMENT_RATE, limit=RankingLimit(2))
    )

    assert found.hint == (
        "Pokazano pierwsze 2 z 4 miast; kolejne pokaże większy limit (najwyżej 100)."
    )


def test_no_city_with_the_indicator_says_so() -> None:
    nothing = IndicatorValues(
        indicator=Indicator.AVERAGE_WAGE,
        period="2025",
        cities=tuple(dataclasses.replace(item, value=None) for item in UNEMPLOYMENT.cities),
    )
    indicators = FakeIndicatorSource(values={Indicator.AVERAGE_WAGE: nothing})

    found = rank(FakeRankingSource(), IndicatorCriteria(Indicator.AVERAGE_WAGE), indicators)

    assert found.ranking.items == ()
    assert found.hint == "Serwis nie podaje tego wskaźnika dla żadnego z 4 miast."


def test_a_slug_that_is_no_location_gets_no_link() -> None:
    odd = IndicatorValues(
        indicator=Indicator.AVERAGE_WAGE,
        period="2025",
        cities=(dataclasses.replace(UNEMPLOYMENT.cities[0], city_slug="War szawa"),),
        section="gus-wynagrodzenia",
    )
    indicators = FakeIndicatorSource(values={Indicator.AVERAGE_WAGE: odd})

    found = rank(FakeRankingSource(), IndicatorCriteria(Indicator.AVERAGE_WAGE), indicators)

    assert found.stats_urls == (None,)
