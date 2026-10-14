"""Contract of ``deweloperuch_mcp.api.dto.investment_sale_events_dto`` with the service's
real answers (the samples in docs/discovery/samples/, the raw payloads in
tests/fixtures/).
"""

from datetime import date

from deweloperuch_mcp.api.dto.investment_sale_events_dto import InvestmentSaleEventsDto
from support.providers.samples import body


def test_investment_sale_events_sample_is_keyed_by_offer_id() -> None:
    parsed = InvestmentSaleEventsDto.model_validate(body("api.inv_sale_events"))

    assert len(parsed.root) == 16
    assert 206087 in parsed.root
    events = parsed.root[2377]
    assert [e.event_type for e in events] == ["OFFER_EVENT", "ARCHIVED_EVENT", "RESTORED_EVENT"]
    assert events[0].event_date == "2025-02-25T00:00:00.000Z"
    assert parsed.root[206087][0].event_data == '{"source":"scraper_pr"}'


def test_iso_dates_in_samples_are_valid_dates() -> None:
    """Every date in the samples is one of the accepted formats (documents [P] formats)."""
    parsed = InvestmentSaleEventsDto.model_validate(body("api.inv_sale_events"))

    dates = {e.event_date for events in parsed.root.values() for e in events}
    assert {d[:10] for d in dates} <= {"2025-02-25", "2026-10-03"}
    assert all(date.fromisoformat(d[:10]) for d in dates)
