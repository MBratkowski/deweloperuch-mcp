# deweloperuch-mcp

Warstwa integracyjna między agentem/LLM a danymi [deweloperuch.pl](https://deweloperuch.pl) (ceny ofertowe deweloperów, transakcje z Rejestru Cen Nieruchomości, statystyki rynku, wycena).

```
deweloperuch.pl → client (JSON API + RSC) → domain/services → CLI + MCP → agent
```

## Status

**Etap 1–2 (discovery + capability matrix): ukończone 2026-10-09.** Implementacja jeszcze się nie zaczęła.

## Dokumentacja

| Dokument | Zawartość |
|---|---|
| [docs/discovery/README.md](docs/discovery/README.md) | Mapa warstwy danych: architektura serwisu, kanały dostępu, kluczowe ustalenia |
| [docs/discovery/endpoints.md](docs/discovery/endpoints.md) | Katalog 34 endpointów `/api/*` i server actions |
| [docs/discovery/pages-rsc.md](docs/discovery/pages-rsc.md) | Strony SSR jako źródło danych: filtry, sortowanie, paginacja, propsy |
| [docs/discovery/entities.md](docs/discovery/entities.md) | Encje, identyfikatory, relacje, słowniki wartości |
| [docs/discovery/samples/](docs/discovery/samples/) | Przycięte próbki odpowiedzi (podstawa testów kontraktowych) |
| [docs/capability-matrix.md](docs/capability-matrix.md) | Capabilities → requesty → CLI / MCP tool → status |
| [docs/open-questions.md](docs/open-questions.md) | Luki, hipotezy, pytania do decyzji |
| [docs/decisions.md](docs/decisions.md) | Decyzje architektoniczne i propozycja pierwszego vertical slice |

## Narzędzia recon

- `python3 recon/scan_bundles.py`: lista aktualnych `/api/*` i server actions z bundli JS (wykrywanie zmian po deployu serwisu)
- `recon/flight.py`: dekoder payloadu RSC (`flight(html_path)`, `find_json_after(text, prop)`)
