"""deweloperuch.pl (D16, D17): the adapters of the use cases' ports (``usecases.ports``).

- ``adapters/``: one ``*Api`` class per resource of the service (``OffersApi``...);
- ``dto/``: the service's data as DTOs with ``to_model()`` (``dto.Dto`` is the base);
- ``queries/``: backend query parameters, one ``*Query`` per list (``OffersQuery``);
- ``http/``: support: the transport (D2 policy, cache, STOP latch), the STOP record, and
  reading a JSON endpoint (``JsonEndpoint``) or an RSC page (``RscPage``);
- ``links``: the ``PageLinks`` port (D12).

Nothing else sits at the top (tests/architecture/test_conventions.py). Backend names (``invest``,
``sale``, ``filterPrice``, prop names) stay in this package. Imports: ``models``,
``usecases.ports``, ``api``, the stdlib modules shared with ``recon/`` and third-party
libraries; never the rest of ``usecases``, the composition root nor the consumers
(tests/architecture/test_layering.py).
"""
