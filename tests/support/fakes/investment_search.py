"""``InvestmentDirectory`` in memory, and the investments it lists."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from deweloperuch_mcp.models.investment_summary import (
    InvestmentMatches,
    InvestmentName,
    InvestmentsLimit,
    InvestmentSummary,
)
from deweloperuch_mcp.models.offer import DeveloperRef
from deweloperuch_mcp.models.values import CitySlug
from deweloperuch_mcp.usecases import ports

KOMFORT = DeveloperRef(
    developer_slug="invest-komfort-spolka-akcyjna", name="Invest Komfort Spółka Akcyjna Sp.K."
)


ATAL = DeveloperRef(developer_slug="atal", name="ATAL S.A.")


def summary(
    name: str,
    *,
    active: int | None = None,
    per_m2: float | None = None,
    price: float | None = None,
    developer: DeveloperRef | None = KOMFORT,
) -> InvestmentSummary:
    slug = InvestmentName.folded(name).replace(" ", "-")
    return InvestmentSummary(
        investment_slug=slug,
        name=name,
        status="active",
        city="Sopot",
        city_slug="sopot",
        developer=developer,
        avg_price=price,
        avg_price_per_m2=per_m2,
        offers_active=active,
    )


CITY = (
    summary("Zielone", active=3, per_m2=21_000.0, price=900_000.0),
    summary("Akacjowe", active=None, per_m2=None, price=None, developer=ATAL),
    summary("Ąkacje", active=12, per_m2=None, price=None),
    summary("Morskie", active=3, per_m2=18_500.5, price=1_200_000.0, developer=ATAL),
    summary("Brzozy", active=0, per_m2=25_000.0, price=700_000.0),
)


@dataclass
class FakeInvestmentDirectory:
    city: tuple[InvestmentSummary, ...] = CITY
    matches: InvestmentMatches = InvestmentMatches(
        (InvestmentSummary(investment_slug="nowy-targ", name="Nowy Targ", offers_active=4),), 1
    )
    error: Exception | None = None
    asked: list[tuple[str, object, object]] = field(default_factory=list)

    def in_city(self, city: CitySlug) -> tuple[InvestmentSummary, ...]:
        self.asked.append(("in_city", city, None))
        if self.error is not None:
            raise self.error
        return self.city

    def by_name(self, name: InvestmentName, limit: InvestmentsLimit) -> InvestmentMatches:
        self.asked.append(("by_name", name, limit))
        if self.error is not None:
            raise self.error
        return self.matches


if TYPE_CHECKING:  # mypy checks that each fake is the port it stands in for
    _investment_directory: ports.InvestmentDirectory = FakeInvestmentDirectory()
