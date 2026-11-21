# Decyzja architektoniczna — ArchPat

Status: **best_in_catalog**.

Wybrany wariant: **modular_monolith**.

Zakres: trzy jawne szablony CQRS + ES. Wynik nie stanowi dowodu optymalności poza katalogiem ani gotowości wykonania.

| Wariant | Dopuszczalny | Nowe procesy | RAM aplikacji / razem [MiB, estymacja] | Koszt |
|---|---:|---:|---:|---:|
| modular_monolith | tak | 1 | 192 / 2240 | 0.24765625 |
| worker_split | tak | 2 | 320 / 2368 | 0.34484375 |
| service_split | nie | 4 | 576 / 2624 | — |

## Uzasadnienie i ograniczenia

- Only three CQRS+ES deployment templates are enumerated; this is not a global solver.
- RAM and change-surface values are editable, unmeasured priors; no latency guarantee is inferred.
- Existing URTime/Autodo/LLM/database processes are excluded from the new-process count; reserve their RAM explicitly.
- Architecture feasibility is structural and conditional on priors, not a production readiness attestation.
- URL/URI/URN/URT runtime contracts and Polycell/Forge adapters need local source verification.
- URN-y example są ilustracyjne; pinning wersji i digestu wykonuje istniejący rejestr danych.
- Rezerwa 2048 MiB jest przykładowym parametrem, nie pomiarem uritime ani modelu LLM.
- Lokalny LLM i usługi ekosystemu są konfigurowane oddzielnie i nie są pobierane przez ArchPat.

### Odrzucenie: service_split

- max_processes: application process count exceeds the limit

## Wymagania wymagające dalszej weryfikacji

- temporal_unresolved: Natural-language time awaits uritime/URT interpretation and binding.
- unbound_implementations: This is an architecture proposal; runtime bindings remain unverified.
- reuse_not_verified: Index/source presence is not proof of contract compatibility.

## Kryteria akceptacji użytkownika

- [ ] Ponowienie tej samej komendy nie tworzy drugiego wyniku.
- [ ] Zapytanie o wynik nie uruchamia ponownie oceny ani innych skutków.
- [ ] Historia pozwala odbudować projekcję bez ponownego wywołania modelu.
- [ ] Ocena korzysta z przypiętej wersji artefaktu, a wynik wskazuje jej URN.
- [ ] Warunek czasu zostaje rozstrzygnięty przez istniejące uritime/URT.

Te kryteria są zachowane jako wymagania. ArchPat nie wykonał testów implementacji systemu docelowego.

