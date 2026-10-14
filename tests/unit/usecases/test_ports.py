"""Tests of ``deweloperuch_mcp.usecases.ports``."""

import datetime as dt

from deweloperuch_mcp.usecases import ports
from support.fakes.buildings import (
    FakeBuildingCatalog,
    FakeBuildingLinks,
)
from support.fakes.catalogs import (
    EchoPageLinks,
    FakeCatalogs,
)
from support.fakes.clocks import CLOCK
from support.fakes.developer_search import FakeDeveloperLinks, FakeDeveloperSearch
from support.fakes.stop import FakeStopControl


def test_the_fakes_are_the_ports() -> None:
    """The fakes satisfy the protocols, so the use cases are tested against the ports."""
    fake = FakeCatalogs()
    directory: ports.LocationDirectory = fake
    catalog: ports.OfferCatalog = fake
    investments: ports.InvestmentCatalog = fake
    source: ports.GovernmentStatisticsSource = fake
    market: ports.CityOffersSource = fake
    developers: ports.DeveloperDirectory = fake
    clock: ports.Clock = CLOCK
    links: ports.PageLinks = EchoPageLinks()
    control: ports.StopControl[str] = FakeStopControl()

    assert all(
        port is fake for port in (directory, catalog, investments, source, market, developers)
    )
    assert clock.today() == dt.date(2026, 10, 13)
    assert isinstance(links, EchoPageLinks) and isinstance(control, FakeStopControl)


def test_the_building_fakes_are_the_ports() -> None:
    catalog: ports.BuildingCatalog = FakeBuildingCatalog()
    pages: ports.BuildingPageLinks = FakeBuildingLinks()

    assert isinstance(catalog, FakeBuildingCatalog) and isinstance(pages, FakeBuildingLinks)


def test_the_developer_search_fakes_are_the_ports() -> None:
    directory: ports.DeveloperSearch = FakeDeveloperSearch()
    links: ports.DeveloperLinks = FakeDeveloperLinks()

    assert isinstance(directory, FakeDeveloperSearch) and isinstance(links, FakeDeveloperLinks)
