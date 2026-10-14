"""Live: ``recon/probe.py``, one request per run (never the bundle scanner: ~140 requests).

The page run checks the fix of 2026-10-10 on the live service: without ``--prop`` the
list of data props now shows ``initialData`` (the data row follows text rows).
"""

import json

import pytest

from support.e2e.live import Budget, run_probe

pytestmark = pytest.mark.live


def test_probe_api(budget: Budget) -> None:
    run = run_probe(budget, "api", "/api/cities?q=krak")

    assert run.code == 0, (run.code, run.stderr)
    data = json.loads(run.stdout)
    assert any(m["city_slug"] == "krakow" for m in data["cityMappings"])


def test_probe_page_lists_the_data_props(budget: Budget) -> None:
    run = run_probe(budget, "page", "/ceny-ofertowe/warszawa/mieszkania?perPage=10")

    assert run.code == 0, (run.code, run.stderr)
    listed = json.loads(run.stdout)
    assert {"name": "initialData", "type": "object", "size": 2} in listed
