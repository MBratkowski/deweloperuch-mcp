"""The models are plain Python and speak the domain's words (D3, D13, D16)."""

import ast
import dataclasses
import re
from typing import Any

import pytest

from deweloperuch_mcp.models.developer_profile import (
    DeveloperCity,
    DeveloperInvestment,
    DeveloperListing,
    DeveloperProfile,
    DeveloperSummary,
)
from deweloperuch_mcp.models.investment import Investment, OfferDetail
from deweloperuch_mcp.models.location import Location, LocationSearchResult
from deweloperuch_mcp.models.market_statistics import (
    DeveloperShare,
    MarketCriteria,
    MarketOffer,
    MarketStatistics,
)
from deweloperuch_mcp.models.offer import (
    DeveloperRef,
    InvestmentRef,
    ListedOffer,
    Offer,
    OfferSearchCriteria,
    OfferSearchPage,
)
from deweloperuch_mcp.models.price_history import PriceEvent, PriceFlags, PriceHistory
from support.checks.layering import MODELS_STDLIB
from support.paths import PACKAGE_SOURCE

BACKEND_NAME = re.compile(r"^(invest|sale)(_|$)|sale|amount|size|sqm|^data$")


DOMAIN_TYPES = (
    Location,
    LocationSearchResult,
    DeveloperRef,
    PriceEvent,
    PriceHistory,
    Offer,
    InvestmentRef,
    ListedOffer,
    OfferSearchCriteria,
    OfferSearchPage,
    Investment,
    OfferDetail,
    PriceFlags,
    MarketOffer,
    MarketStatistics,
    MarketCriteria,
    DeveloperShare,
    DeveloperInvestment,
    DeveloperCity,
    DeveloperSummary,
    DeveloperProfile,
    DeveloperListing,
)


SOURCE = PACKAGE_SOURCE / "models"


@pytest.mark.parametrize("module", sorted(path.name for path in SOURCE.glob("*.py")))
def test_the_domain_is_plain_python(module: str) -> None:
    """Only the standard library's values, types and arithmetic (the allowlist of
    tests/architecture/test_layering.py) and the domain itself: no pydantic, no I/O (D13)."""
    tree = ast.parse((SOURCE / module).read_text(encoding="utf-8"))
    imported = {
        node.module if isinstance(node, ast.ImportFrom) else alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import | ast.ImportFrom)
        for alias in node.names
    }

    own = {name for name in imported if name and name.startswith("deweloperuch_mcp")}
    assert all(name.startswith("deweloperuch_mcp.models.") for name in own), own
    assert {name for name in imported if name} - own <= MODELS_STDLIB


@pytest.mark.parametrize("kind", DOMAIN_TYPES)
def test_domain_names_are_not_the_backend_ones(kind: type[Any]) -> None:
    names = {field.name for field in dataclasses.fields(kind)}
    names |= {name for name in vars(kind) if not name.startswith("_")}

    assert not {name for name in names if BACKEND_NAME.search(name)}
