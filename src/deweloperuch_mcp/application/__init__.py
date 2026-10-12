"""Use cases (D13): one per operation, over the ports of the domain.

They take domain values, call the ports, apply the domain's rules and say in the
domain's terms what a failure of the service is about (``failures.reported_as``). They
know neither the service nor its backend names; links to public pages come through the
``PageLinks`` port. Imports: the domain and the standard library only
(tests/test_layering.py).
"""
