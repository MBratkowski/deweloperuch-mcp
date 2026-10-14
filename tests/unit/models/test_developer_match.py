"""Tests of ``deweloperuch_mcp.models.developer_match``."""

import pytest

from deweloperuch_mcp.models.developer_match import (
    DEFAULT_MATCHES,
    MAX_MATCHES,
    DeveloperMatches,
    DeveloperName,
    DeveloperSearchResult,
    MatchCount,
)
from deweloperuch_mcp.models.errors import InvalidValueError, TextLength, ValueName, WholeNumber
from support.builders.developer_search import matches
from support.fakes.developer_search import ATAL


def test_a_developer_name_is_trimmed_and_keeps_its_letters() -> None:
    assert DeveloperName.parse("  Dom Development ") == DeveloperName("Dom Development")
    assert DeveloperName.parse("Śląskie") == DeveloperName("Śląskie")


@pytest.mark.parametrize("given", ["a", " a ", "", "x" * 101, None, 42])
def test_a_developer_name_needs_2_to_100_characters(given: object) -> None:
    with pytest.raises(InvalidValueError) as caught:
        DeveloperName.parse(given)

    assert caught.value.value is ValueName.DEVELOPER_NAME
    assert caught.value.rule == TextLength(2, 100)
    assert caught.value.given == given


def test_the_count_of_matches_is_the_uis_5_by_default() -> None:
    """[P] docs/discovery/endpoints.md: the UI asks for 5 (sample ``api.developers_q``)."""
    assert MatchCount().value == DEFAULT_MATCHES == 5
    assert MAX_MATCHES == 20
    assert MatchCount.parse(20).value == 20


@pytest.mark.parametrize("given", [0, 21, -1, True, "5", 5.0, None])
def test_the_count_of_matches_is_a_whole_number_from_1_to_20(given: object) -> None:
    with pytest.raises(InvalidValueError) as caught:
        MatchCount.parse(given)

    assert caught.value.value is ValueName.DEVELOPER_MATCHES
    assert caught.value.rule == WholeNumber(1, 20)


def test_a_complete_result_has_its_total() -> None:
    result = DeveloperSearchResult.of(
        DeveloperName("atal"), MatchCount(), DeveloperMatches((ATAL,), total=1, more=False)
    )

    assert result.items == (ATAL,)
    assert (result.total, result.returned, result.truncated) == (1, 1, False)


def test_more_matches_than_shown_is_truncated_with_the_services_total() -> None:
    result = DeveloperSearchResult.of(
        DeveloperName("dom"), MatchCount(), matches(5, total=12, more=True)
    )

    assert (result.total, result.returned, result.truncated) == (12, 5, True)


def test_a_total_above_what_was_shown_is_truncated_even_without_more() -> None:
    result = DeveloperSearchResult.of(
        DeveloperName("dom"), MatchCount(), matches(5, total=6, more=False)
    )

    assert (result.total, result.returned, result.truncated) == (6, 5, True)


def test_matches_beyond_the_count_are_cut_and_the_cut_is_explicit() -> None:
    """[W] a ``limit`` other than 5 is honoured; if the service ever gives more, the
    result still shows at most the count asked for and says so (D4)."""
    result = DeveloperSearchResult.of(
        DeveloperName("dom"), MatchCount(3), matches(7, total=7, more=False)
    )

    assert [item.developer_slug for item in result.items] == ["dev-0", "dev-1", "dev-2"]
    assert (result.total, result.returned, result.truncated) == (7, 3, True)


@pytest.mark.parametrize(
    ("given", "total", "more", "expected"),
    [
        (5, 5, True, (None, 5, True)),  # more, but a total of only what came
        (5, 3, False, (5, 5, False)),  # a total below what came: what came
        (5, 3, True, (None, 5, True)),
        (5, None, True, (None, 5, True)),
        (2, None, False, (2, 2, False)),
    ],
)
def test_a_total_that_does_not_fit_what_came_is_not_shown(
    given: int, total: int | None, more: bool, expected: tuple[int | None, int, bool]
) -> None:
    result = DeveloperSearchResult.of(
        DeveloperName("dom"), MatchCount(), matches(given, total=total, more=more)
    )

    assert (result.total, result.returned, result.truncated) == expected


def test_nothing_found_is_a_total_of_0() -> None:
    result = DeveloperSearchResult.of(
        DeveloperName("xyzzy"), MatchCount(), matches(0, total=0, more=False)
    )

    assert (result.total, result.returned, result.truncated, result.items) == (0, 0, False, ())
