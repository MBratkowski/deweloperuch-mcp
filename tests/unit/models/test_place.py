"""Tests of ``deweloperuch_mcp.models.place``."""

import pytest

from deweloperuch_mcp.models.place import Place


def test_a_place_is_the_one_asked_for_by_its_slug() -> None:
    place = Place(name="Ignatki-osiedle", slug="ignatki-osiedle")

    assert place.is_named("ignatki-osiedle")
    assert not place.is_named("ignatki")


def test_a_place_is_a_value() -> None:
    place = Place(name="Kraków", slug="krakow")

    assert place == Place(name="Kraków", slug="krakow")
    with pytest.raises(AttributeError):
        place.name = "Krakowiany"  # type: ignore[misc]
