"""The samples' trimming markers (CLAUDE.md, "Próbki") and the helper that removes them."""

from support.providers.samples import untrimmed


def test_untrimmed_removes_only_the_markers() -> None:
    value = {
        "a": ["x", "... (2 more, 3 total)"],
        "b": {"1": [1, "... (5 more, 6 total)"], "...": "40 more keys"},
        "c": ["... (2 more, 3 total) but not a marker", "text"],
    }

    assert untrimmed(value) == {
        "a": ["x"],
        "b": {"1": [1]},
        "c": ["... (2 more, 3 total) but not a marker", "text"],
    }
