"""What never reaches the model (D3, D12) and how big a result may be (S1b)."""

import re

# D3: backend names never reach the model (keys of results, descriptions, schemas).
BACKEND_NAMES = re.compile(r"sale|invest(?!ment)|amount|_rsc|\brsc\b|/api/|initialData", re.I)


# Error results: no paths, prop names or text of the service's answer either.
LEAKS = re.compile(
    r"/api|/ceny-|/statystyki|initialData|tocItems|currentSlug|invest(?!ment)|sale|"
    r"Ignore previous|<html",
    re.I,
)


SIZE_BUDGET = 8_000
"""Characters of a result that fit the model's context comfortably (S1b)."""


SIZE_BUDGET_50 = 27_500
"""Characters of a page of 50 offers: the per_page description promises about 25k (with
``developer_slug`` since 2026-10-13)."""
