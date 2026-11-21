# ARP-002: Zweryfikowana macierz kontraktów (`uritime`, `URT`, `autodo`, `Forge`)

Data weryfikacji na PC: **2026-11-21**  
Poziom dowodu: **`contract_verified`** (walidacja uruchomiona przeciwko rzeczywistym pakietom lokalnym, patrz [evidence/source-lock.json](../evidence/source-lock.json) oraz [evidence/contract-corpus.json](../evidence/contract-corpus.json)).

## 1. Zgodność z istniejącym planem autonomii

Zgodnie z `docs/ROADMAP.md` przed tworzeniem nowych integracji odczytano istniejące źródła w `/home/tom/github/uritime`:

- `planning/urt-polycell-forge-autonomy.md` (128 215 B, `sha256: 0b731192ebac02ba…`)
- `planning/autonomy-pilot/README.md` (`sha256: 27b2f545a3871172…`)
- `planning/autonomy-pilot/contracts/cells/backlog.reconciliation.cell.yaml` (`sha256: 70efe00c9d0ba6a8…`)
- `planning/autonomy-pilot/cells/python/backlog_reconciliation.py` (`sha256: 646935c3e858f22a…`)

Istniejący pilot już łączy: **URT resolution → komórkę Polycell (`backlog.reconciliation`) → Forge `run_bounded` → Heyasa `AutodoOwnershipStore`**. ArchPat **nie tworzy równoległego stosu autonomii** — pełni rolę właściciela propozycji architektury docelowej (`execution_ready: false`) i dostarcza powiązanie z tymi samymi kontraktami upstream.

## 2. Macierz kontraktów i właścicieli

| Obszar | Repozytorium i przypięty commit | Kontrakt / Schemat | Zweryfikowane publiczne wejścia | Właściciel / granica odpowiedzialności |
|---|---|---|---|---|
| **Propozycja architektury** | `semcod/archpat` (lokalne `0.1.0`) | `archpat.story/v1`, `archpat.graph/v1`, `archpat.synthesis/v1` | `synthesize()`, `validate_operation()`, `diff_graphs()`, `impact()` | ArchPat tworzy wyłącznie propozycję (`execution_ready: false`); brak uprawnień wykonania |
| **Czas (URT)** | `uritime/urt` (`54b52d90bf60`, `0.2.0`, clean) | `urt.temporal-intent/v1`, `urt.resolution/v1`, `descriptor-v1` | `validate_temporal_intent()`, `resolve_temporal_intent()`, `validate_event_selector()` | Wyłącznie `uritime_urt` waliduje i rozwiązuje czas; `context.timezone` musi być jawnie przypięty (nigdy wnioskowany z `locale`) |
| **Komendy, zapytania i fakty CQRS/ES** | `uritime/uritime` (`6fbeb64fa5ff`, `0.1.0`, clean) | `ur.command-envelope/v1`, `ur.domain-event/v1`, `ur.timeline-query/v1`, `ur.plan-projection/v1`, `urt.record/v1` | `validate_command_envelope()`, `validate_query_envelope()`, `export_store_to_urt_records()`, `UriEventStore` | `urievents` pilnuje content-pinningu wejść (`urn:sha256:` lub `content_sha256`) dla `decision_mode="accepted"` oraz zakazu podszywania się `query` pod `command` |
| **Plan / Harmonogram** | `uritime/uritime` (`6fbeb64fa5ff`) | `PlanLedger`, `PlanQueries` | `propose_plan()`, `accept_plan()`, `revise_schedule()`, `cancel_plan()`, `get_plan()`, `rebuild_from_events()`, `query_knowledge_at()` | Pojedynczy właściciel akceptacji: `actor="uritime"` (`OwnershipViolationError` dla `"archpat"`); CAS przez `expected_version` (`PlanConflictError`); `get_plan` i `rebuild_from_events` są czysto odczytowe |
| **Deskryptory operacji** | `uritime/autodo` (`cd434216584a`, `0.2.0`, clean) | `ur.operation-descriptor/v1`, `ur.operation-activity/v1` | `canonical_operation_uri()`, `parse_operation_uri()` | `urn:poa:<op_id>#v<version>`; fail-closed odrzucenie schematów URL (`http`, `https`, `file`, `ws`, `ssh`, …) rzucając `Conflict` |
| **Snapshoty i kwalifikacja patchy** | `heyasa/forge` (`e67afb42edb2`, dirty=21) | `heyasa-forge.project-snapshot/v1`, `heyasa-forge.project-job/v1`, `heyasa-forge.project-job-publication/v1`, `IMPACT_URI` | `SnapshotStore.capture()`, `project_jobs.{prepare,run_checks,publish_precondition}()`, `contracts.validate_input()` | Forge wydaje wyłącznie decyzję (`authority: "decision_only; the caller applies the patch under its own lease"`); nie zapisuje do repozytorium docelowego |
| **Komórki logiki** | `wellmanifest/polycell` (`a50bd58a2656`, clean) | `wellmanifest.polycell.cell/v1`, `poa.process/v1`, `poa.plan/v1` | `standard/polycell-cell.schema.v1.json`, `standard/conformance.py` | Kontrakt YAML jako SSOT dla czystych komórek wymienianych całymi plikami |
| **Action URI / NL-DSL** | `wellmanifest/nl-uri-dsl-llm` (`29a67748a41b`, `1.5.0`, clean) | `process-uri.schema.json`, `semantic-v1.json` | JSON Schema Draft 2020-12 (`format: uri`) | Kanoniczna kopia `process-uri.schema.json` jest bajt-w-bajt identyczna z kopią w Forge |
| **Analiza as-is** | `autogrammar/code2schema` (`c4a0f3b8a3f6`, `0.1.9`, Apache-2.0, dirty=15) | `SchemaIR`, `CQRSRole` | `extract_project()`, `extract_module()`, `analyze()` | Źródło hipotez o istniejącym kodzie; `LICENSE` potwierdza Apache-2.0 (rozwiązuje wzmiankę o rozbieżności z PyPI) |
| **Granice ekstrakcji** | `deconnected` | — | — | **Brak lokalnego checkoutu** (`missing_local_checkout` w `source-lock.json`) |

## 3. Rozróżnienie stanów (bez heurystyki nazw)

| Stan | Reprezentacja w upstream | `dispatch_eligible` / skutek |
|---|---|---|
| **Propozycja architektury (ArchPat)** | `archpat.synthesis/v1` (`execution_ready: false`) | Brak wykonania; artefakt projektowy |
| **Propozycja planu (nieprzyjęta)** | `plan.proposed` (`record_class="proposed_plan"`) | `dispatch_eligible: false`; nie uruchamia wykonania |
| **Przyjęty plan (autorytatywny)** | `plan.accepted` / `plan.revised` (`record_class="accepted_plan"`, `actor="uritime"`, CAS `expected_version`) | `dispatch_eligible: true`, wersjonowane `active_revision` |
| **Rozstrzygnięcie czasu (URT)** | `urt.resolution/v1` (`status`: `resolved` \| `waiting` \| `needs_clarification` \| `rejected`) | `dispatch_allowed: true` tylko przy `status="resolved"` i jednoznacznym `resolved_urt` (`urt:v1:...`) |
| **Fakt zaobserwowany (audyt)** | `ur.domain-event/v1` + `urt.record/v1` CloudEvents | Niemutowalny zapis; `PlanQueries.rebuild_from_events()` odtwarza projekcję bez I/O i bez skutków |
| **Decyzja kwalifikacji Forge** | `heyasa-forge.project-job-publication/v1` (`publishable: true|false`, `reasons: [...]`) | `authority: "decision_only"`; zmiana commita bazowego zatrzymuje publikację kodem `base_snapshot_changed` |

## 4. Rzeczywiste inwarianty wykryte podczas uruchomienia na PC

Podczas bezpośredniego uruchomienia kodu upstream w pilocie ([src/archpat/pilot_uritime_forge.py](../src/archpat/pilot_uritime_forge.py)) potwierdzono cztery krytyczne wymagania, których nie widać było w samych indeksach `code2llm`:

1. **`uritime_urt.selectors.validate_event_selector`**: wymaga jawnych pól `domain` (`observed_event` | `accepted_plan_occurrence` | `proposal` | `forecast`), `source`, `stream`, niepustego `scope`, `order`, `late_policy`, `tie_breaker`, `on_missing` oraz `start_cursor` (`store_id`, `generation >= 1`, `sequence >= 0`).
2. **`uritime.plan_queries._project_plan_events`**: zwraca schemat `ur.plan-projection/v1` z kluczami `active_revision`, `status`, `revisions`, `proposal_branches` oraz `dispatchable_occurrences` (a nie `version`/`occurrences`).
3. **`forge_base.snapshots.SnapshotStore`**: fail-closed odrzuca ulotne systemy plików RAM (`tmpfs`, np. `/tmp` na tym hoście) błędem `SNAPSHOT-INVALID: Snapshot authority must be outside volatile RAM storage`. Magazyn snapshotów musi leżeć na trwałym dysku.
4. **`forge_base.project_jobs.run_checks` + `publish_precondition`**: każde narzędzie testowe modyfikujące drzewo robocze (w tym zwykły `python -m unittest` tworzący `__pycache__/*.pyc`) powoduje odrzucenie publikacji kodem `checks_modified_the_tested_tree`. Komendy Python w Forge muszą używać flagi `-B` (`PYTHONDONTWRITEBYTECODE=1`).
