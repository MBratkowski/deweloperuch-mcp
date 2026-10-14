"""The models (D3, D16, D17; the D13 domain): value objects, entities, aggregates and their
rules; plain Python, frozen dataclasses with their behaviour as methods, one module per
concept, named after it (``offer``, ``price_history``).

No I/O, no pydantic, no backend names, nothing of the package outside ``models``
(tests/architecture/test_layering.py). The ports the use cases depend on are ``usecases.ports``.
"""
