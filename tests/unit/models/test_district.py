"""Tests of ``deweloperuch_mcp.models.district``."""

import pytest

from deweloperuch_mcp.models.district import District
from deweloperuch_mcp.models.values import DistrictName

SRODMIESCIE = District(name="Śródmieście", slug="srodmiescie")
PRAGA_POLNOC = District(name="Praga-Północ", slug="praga-polnoc")


@pytest.mark.parametrize("asked", ["Śródmieście", "ŚRÓDMIEŚCIE", "srodmiescie", "SrOdMiEsCiE"])
def test_district_match_folds_case_and_letters(asked: str) -> None:
    assert SRODMIESCIE.is_named(DistrictName(asked))


@pytest.mark.parametrize("asked", ["Praga Północ", "praga - polnoc", "PRAGA–PÓŁNOC", "pragapolnoc"])
def test_district_match_folds_spaces_and_dashes(asked: str) -> None:
    assert PRAGA_POLNOC.is_named(DistrictName(asked))


@pytest.mark.parametrize("asked", ["Praga-Południe", "Praga", "Śródmieście Północne", "Ωμέγα"])
def test_another_name_does_not_match(asked: str) -> None:
    assert not PRAGA_POLNOC.is_named(DistrictName(asked))


def test_a_name_without_letters_or_digits_matches_nothing() -> None:
    """Folded to nothing, it would match any other such name."""
    assert not District(name="--", slug="x").is_named(DistrictName("??"))


@pytest.mark.parametrize(
    ("name", "asked"), [("Łódź", "lodz"), ("Żółć Ęą", "zolc ea"), ("Ńś Ćź", "NS-CZ")]
)
def test_every_polish_letter_folds(name: str, asked: str) -> None:
    assert District(name=name, slug="x").is_named(DistrictName(asked))
