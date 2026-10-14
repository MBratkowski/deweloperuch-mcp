"""Tests of ``deweloperuch_mcp.consumers.shared.choices``."""

from typing import get_args

import pytest

from deweloperuch_mcp.consumers.shared import choices
from deweloperuch_mcp.consumers.shared.choices import (
    DatasetChoice,
    InvestmentSortChoice,
    PageSizeChoice,
    SortChoice,
    StatusChoice,
)
from deweloperuch_mcp.models.government_statistics import Dataset
from deweloperuch_mcp.models.investment_summary import InvestmentSort
from deweloperuch_mcp.models.transaction_series import Granularity
from deweloperuch_mcp.models.values import DEFAULT_PAGE_SIZE, PAGE_SIZES, OfferSort, OfferStatus


def test_the_choices_of_the_options_are_the_domains() -> None:
    """The ``Literal`` types of the options are projections of the domain's value sets."""
    assert get_args(SortChoice) == tuple(sort.value for sort in OfferSort)
    assert get_args(StatusChoice) == tuple(status.value for status in OfferStatus)
    assert get_args(PageSizeChoice) == PAGE_SIZES
    assert choices.DEFAULT_PAGE_SIZE == DEFAULT_PAGE_SIZE


@pytest.mark.usefixtures("unix_sockets_for_the_event_loop")
def test_the_sort_choices_are_the_domains() -> None:
    assert get_args(InvestmentSortChoice) == tuple(sort.value for sort in InvestmentSort)


@pytest.mark.usefixtures("unix_sockets_for_the_event_loop")
def test_mcp_dataset_names_are_the_domain_ones() -> None:
    assert get_args(DatasetChoice) == tuple(dataset.value for dataset in Dataset)


@pytest.mark.usefixtures("unix_sockets_for_the_event_loop")
def test_the_mcp_granularities_are_the_domains() -> None:
    assert get_args(choices.GranularityChoice) == tuple(item.value for item in Granularity)
    assert Granularity.MONTH.value == choices.DEFAULT_GRANULARITY
