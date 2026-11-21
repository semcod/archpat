# Decyzja architektoniczna — ArchPat

Status: **no_feasible_catalog_candidate**.

Wybrany wariant: **brak dopuszczalnego wariantu**.

Zakres: trzy jawne szablony CQRS + ES. Wynik nie stanowi dowodu optymalności poza katalogiem ani gotowości wykonania.

| Wariant | Dopuszczalny | Nowe procesy | RAM aplikacji / razem [MiB, estymacja] | Koszt |
|---|---:|---:|---:|---:|
| modular_monolith | nie | 1 | 192 / 192 | — |
| worker_split | nie | 2 | 320 / 320 | — |
| service_split | nie | 4 | 576 / 576 | — |

## Uzasadnienie i ograniczenia

- Only three CQRS+ES deployment templates are enumerated; this is not a global solver.
- RAM and change-surface values are editable, unmeasured priors; no latency guarantee is inferred.
- Existing URTime/Autodo/LLM/database processes are excluded from the new-process count; reserve their RAM explicitly.
- Architecture feasibility is structural and conditional on priors, not a production readiness attestation.
- URL/URI/URN/URT runtime contracts and Polycell/Forge adapters need local source verification.
- URN-y example są ilustracyjne; pinning wersji i digestu wykonuje istniejący rejestr danych.
- Rezerwa 2048 MiB jest przykładowym parametrem, nie pomiarem uritime ani modelu LLM.
- Lokalny LLM i usługi ekosystemu są konfigurowane oddzielnie i nie są pobierane przez ArchPat.

### Odrzucenie: modular_monolith

- ram_budget_mb: estimated target + reserved RAM exceeds the budget

### Odrzucenie: worker_split

- ram_budget_mb: estimated target + reserved RAM exceeds the budget

### Odrzucenie: service_split

- ram_budget_mb: estimated target + reserved RAM exceeds the budget
- max_processes: application process count exceeds the limit
