"""``ValuationSource`` in memory: answers or raises what the test gives, records the subjects."""

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from deweloperuch_mcp.models.valuation import (
    Valuation,
    ValuationSubject,
)
from deweloperuch_mcp.usecases import ports


@dataclass
class FakeValuationSource:
    answer: Valuation | Exception
    asked: list[ValuationSubject] = field(default_factory=list)

    def valuation(self, subject: ValuationSubject) -> Valuation:
        self.asked.append(subject)
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


if TYPE_CHECKING:  # mypy checks that each fake is the port it stands in for
    _valuation_source: ports.ValuationSource = FakeValuationSource(Exception())
