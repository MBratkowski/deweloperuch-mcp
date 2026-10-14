"""Contract of ``deweloperuch_mcp.api.dto.sale_events_dto`` with the service's real answers
(the samples in docs/discovery/samples/, the raw payloads in tests/fixtures/).
"""

from deweloperuch_mcp.api.dto import sale_events_dto
from support.providers.samples import body


def test_sale_events_sample() -> None:
    parsed = sale_events_dto.SaleEventsDto.model_validate(body("api.sale_events"))

    assert parsed.success is True
    assert parsed.saleData is not None
    assert (parsed.saleData.name, parsed.saleData.amount) == ("C224", "1620175")
    assert [e.sale_event_id for e in parsed.events] == [145581, 510028, 841366]
    assert [e.amount for e in parsed.events] == ["1620000", "1620000", "1620175"]
    assert parsed.events[1].source == ""
