# Dowód pilotażu pionowego na PC (Sekcja 12 + ARP-001..ARP-003)

Data wykonania: **2026-11-21**  
Środowisko: Linux, Python 3.13.12 (`.venv` w `/home/tom/github/semcod/archpat/.venv`), bez modyfikacji żadnego repozytorium sąsiedniego.

## 1. Uruchomione komendy weryfikacyjne

```bash
cd /home/tom/github/semcod/archpat
.venv/bin/python scripts/run_pilot.py
.venv/bin/python -m unittest discover -s tests -v
```

Wynik testów jednostkowych i integracyjnych: **79/79 OK** (77 bazowych testów ArchPat 0.1.0 + 2 nowe testy integracyjne w [tests/test_pilot_uritime_forge.py](../tests/test_pilot_uritime_forge.py)).

## 2. Wygenerowane artefakty dowodowe

- [evidence/source-lock.json](source-lock.json) — **12/13** lokalnych checkoutów zweryfikowanych (`source_verified`), **1** jawny brak (`deconnected`: `missing_local_checkout`).
- [evidence/contract-corpus.json](contract-corpus.json) — **16/16** pozytywnych i negatywnych walidacji kontraktów (`contract_verified`).
- [evidence/pilot-result.json](pilot-result.json) — wynik pionowego pilotażu dla `examples/story-local.json` (`exercise-feedback`, poziom: `integration_verified` dla spiętej ścieżki lokalnej; propozycja ArchPat zachowuje `execution_ready: false`).

## 3. Spięcie wszystkich 5 kryteriów akceptacji `exercise-feedback` + Forge

| Kryterium / inwariant | Rzeczywisty komponent upstream | Wynik | Dowód z `pilot-result.json` |
|---|---|---|---|
| **Propozycja ArchPat** | `archpat.synthesis.synthesize()` | **PASS** | `selected_variant: "modular_monolith"`, `execution_ready: false`, `graph_sha256: bf531bca2ec70665…` |
| **Kryterium 1: idempotencja komendy (`request-review`)** | `urievents.contracts.CommandEnvelope` + `uritime.plan_commands.PlanLedger` | **PASS** | `urn:poa:exercise.review#v1`, ponowne `accept_plan(expected_version=0)` rzuca `PlanConflictError`; liczba zdarzeń nie rośnie (`2 -> 2`) |
| **Kryterium 2: zapytanie bez skutków (`get-feedback`)** | `urievents.validate_query_envelope()` + `uritime.plan_queries.PlanQueries.get_plan()` | **PASS** | `events_before_query: 2 == events_after_query: 2`, `active_revision: 1`, `status: "accepted"` |
| **Kryterium 3: czysta odbudowa projekcji (replay)** | `PlanQueries.rebuild_from_events()` | **PASS** | `replay_matches_live: true` bez wywołań I/O ani efektów ubocznych |
| **Kryterium 4: przypięty URN artefaktu** | `urievents.contracts.DataRef` (`urn:sha256:...`) + `validate_command_envelope()` | **PASS** | `urn:sha256:5b45f6001c99821d…`; nieprzypięty URN w teście negatywnym odrzucony |
| **Kryterium 5: rozstrzygnięcie czasu URT** | `uritime_urt.resolution.resolve_temporal_intent()` | **PASS** | `resolved_urt: "urt:v1:interval:2026-11-21T09:15:00Z/2026-11-21T09:55:00Z"` (po zdarzeniu `artifact.submitted` 09:15Z, 5 min przed nast. ćwiczeniem 10:00Z w `Europe/Warsaw`) |
| **Granica ownership planu** | `PlanLedger.accept_plan(actor="archpat")` | **PASS** | Odrzucone przez `OwnershipViolationError` (jedynym właścicielem akceptacji jest `uritime`) |
| **Eksport URT Record v1 (CloudEvents)** | `urievents.contracts.export_store_to_urt_records()` | **PASS** | 2 zwalidowane rekordy CloudEvents (`urt-record-v1.schema.json` + `urt-record-data-v1.schema.json`) |
| **Punkt kwalifikacji Forge (świeży snapshot)** | `forge_base.snapshots.SnapshotStore` + `project_jobs.{prepare,run_checks,publish_precondition}` | **PASS** | `checks_status: "PASS"` (`python -B -m unittest`), `publishable: true`, `authority: "decision_only; the caller applies the patch under its own lease"` |
| **Punkt kwalifikacji Forge (nieaktualny snapshot)** | `publish_precondition()` po równoległym commicie w repo docelowym | **PASS** | `publishable: false`, `reasons: ["base_snapshot_changed"]` |

## 4. Uczciwe granice i co nadal pozostaje otwarte

- **Lokalny katalog, nie repozytorium Git**: `/home/tom/github/semcod/archpat` nie jest jeszcze zainicjalizowanym repozytorium Git ani zdalnym `semcod/archpat` (sprawdzono read-only przez `gh repo view semcod/archpat` — repozytorium nie istnieje).
- **Brak `deconnected`**: narzędzie nie jest sklonowane lokalnie (`missing_local_checkout`).
- **Brak żywego wykonania LLM / Autodo dispatch**: pilotaż weryfikuje 1 komendę i 1 zapytanie w izolowanym SQLite `UriEventStore` oraz kwalifikację patchy w izolowanym repozytorium Git Forge; nie uruchamia produkcyjnych usług, zewnętrznych konektorów ani zdalnego LLM.
- **Niezmierzone metryki RAM/opóźnień**: estymaty RAM w `archpat synthesize` nadal mają jawny status `heuristic_unmeasured` (pomiary PC należą do `ARP-015`).
