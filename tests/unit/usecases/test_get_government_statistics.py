"""Tests of ``deweloperuch_mcp.usecases.get_government_statistics``."""

import pytest

from deweloperuch_mcp.models.errors import (
    NotFoundError,
)
from deweloperuch_mcp.models.government_statistics import (
    Dataset,
    Frequency,
    LocationStatistics,
    PeriodCount,
    SeriesPoint,
    StatisticsTable,
    TimeSeries,
    Unit,
)
from deweloperuch_mcp.models.values import LocationSlug
from deweloperuch_mcp.usecases.get_government_statistics import (
    GetGovernmentStatistics,
    GetGovernmentStatisticsRequest,
    GetGovernmentStatisticsResult,
)
from support.fakes.catalogs import EchoPageLinks, FakeCatalogs, published


def test_statistics_come_with_the_link_to_their_section() -> None:
    fake = FakeCatalogs(published=published("warszawa"))

    found = GetGovernmentStatistics(fake, EchoPageLinks()).execute(
        GetGovernmentStatisticsRequest(
            location=LocationSlug("warszawa"), dataset=Dataset.UNEMPLOYMENT, periods=PeriodCount(1)
        )
    )

    assert fake.calls == ["location_statistics warszawa unemployment"]
    assert found.statistics.returned == 1
    assert found.stats_url == "stats:warszawa#gus-x"


def test_truncated_statistics_say_how_to_see_older_periods() -> None:
    series = TimeSeries(
        "rate", "Stopa", Unit.PERCENT, tuple(SeriesPoint(str(y), 1.0) for y in range(2001, 2026))
    )
    table = StatisticsTable(Dataset.UNEMPLOYMENT, Frequency.YEAR, "GUS", (series,), None)
    published = LocationStatistics(LocationSlug("x"), "X", {table.dataset: table})

    cut = published.statistics(Dataset.UNEMPLOYMENT, PeriodCount(3))
    whole = published.statistics(Dataset.UNEMPLOYMENT, PeriodCount(25))

    assert GetGovernmentStatisticsResult(statistics=cut, stats_url=None).hint == (
        "Pokazano ostatnie 3 z 25 okresów (dane od 2001); starsze pokaże większa wartość periods."
    )
    assert GetGovernmentStatisticsResult(statistics=whole, stats_url=None).hint is None


def test_a_dataset_not_published_is_the_domains_message_unwrapped() -> None:
    fake = FakeCatalogs(published=published("warszawa"))

    with pytest.raises(NotFoundError) as caught:
        GetGovernmentStatistics(fake, EchoPageLinks()).execute(
            GetGovernmentStatisticsRequest(
                location=LocationSlug("warszawa"), dataset=Dataset.WAGES, periods=PeriodCount()
            )
        )

    assert str(caught.value).startswith("Serwis nie publikuje zestawu 'wages'")


def test_an_unknown_location_says_what_to_give() -> None:
    fake = FakeCatalogs(errors={"location_statistics x unemployment": NotFoundError("404")})

    with pytest.raises(
        NotFoundError, match="^Serwis nie ma statystyk rządowych dla lokalizacji 'x'"
    ):
        GetGovernmentStatistics(fake, EchoPageLinks()).execute(
            GetGovernmentStatisticsRequest(
                location=LocationSlug("x"), dataset=Dataset.UNEMPLOYMENT, periods=PeriodCount()
            )
        )
