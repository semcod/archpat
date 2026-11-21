# Integracje i ponowne użycie kodu

Archpat projektuje warianty grafu architektury oraz przepływów dla user story.
Wersja 0.1 rozpoznaje kandydatów do ponownego użycia z indeksów code2llm i może
odczytać AST wskazanych źródeł na PC. **Nie wdraża runtime adapterów do uritime,
Autodo, Forge ani Polycell.** Wskazana niżej metoda jest miejscem do sprawdzenia,
a nie obietnicą zgodności jej podpisu lub schematu danych.

## Źródła i poziomy dowodu

Mapa poniżej pochodzi z dołączonego indeksu `uritime` z 2026-11-21. Nagłówek
indeksu raportuje 647 plików, 1856 funkcji i 192 klasy. Nie oznacza to odczytu
647 źródeł: załącznik zawiera nazwy, liczby i fragmenty opisów symboli.

`parse_toon()` czyta tekstowy format `M[count]:` i `D:`. Nie jest parserem ogólnego
YAML. Zachowuje SHA-256 dokładnych bajtów indeksu. Pola `reported_*` są deklaracją
producenta indeksu, a `parsed_*` opisują wynik parsera; rozbieżność jest widoczna.

`match_reuse()` stosuje jawny ranking leksykalny nazw i symboli. Jego `score` jest
sumą trafień nazw, nie prawdopodobieństwem zgodności ani oceną jakości projektu.
Każdy wynik ma `evidence="indexed_only"`, `api_verified=false`.

`probe_workspace()` sprawdza wyłącznie pliki pod jawnie przekazanym korzeniem.
Odrzuca ścieżki absolutne, `..` i dowiązania symboliczne. Dla Python wykonuje
odczyt, SHA-256 i analizę AST; nie importuje ani nie uruchamia źródeł. Inne pliki
sprawdza przez metadane. Wynik `source_ast_only` wciąż nie potwierdza runtime API.
Brak definicji w AST może wynikać również z reexportu lub dynamicznego API.

Docelowy proces wiązania implementacji rozróżnia:

1. Wymaganą capability w grafie teoretycznym.
2. Kandydata wskazanego indeksem.
3. Źródło zaobserwowane w konkretnym snapshotcie.
4. Binding dopasowany do rzeczywistego kontraktu i wersji zależności.
5. Wynik lokalnej kwalifikacji integracji i zapis evidence.

Archpat 0.1 realizuje pierwsze trzy etapy w zakresie opisanym w README. Etapy
czwarty i piąty wymagają źródeł i środowiska użytkownika.

## Właściciele odpowiedzialności

| Projekt | Właściciel odpowiedzialności | Rola Archpat |
|---|---|---|
| `uritime_urt` | Semantyka czasu, temporal AST, resolution, recurrence, canonicalizacja | Referencje do czasu i adapter do istniejącego walidatora |
| `uritime` + `urievents` | Plan/Schedule, pojedynczy właściciel, propozycje, akceptacja, projekcje | Eksport propozycji planu, odczyt istniejących kontraktów |
| Autodo / `subactor_autonomy` | Goal/Action, dispatch, skutki, receipts, pinning danych | Opis wymaganych capability i odwzorowanie operacji |
| `autonom` | Decyzje i synteza kandydatów | Opcjonalny dostawca kandydatów; bez równoległego ownership celu |
| SubLLM | Inferencja i role modelowe | Port modelu, odpowiedzi strukturalne |
| `urtlog` | Rejestr URL/URI/URN/URT, logi i widoki | Eksport oraz obserwacja; ustalenie jednego toru wykonania |
| Forge | Kwalifikacja, snapshoty i katalog możliwości według własnych kontraktów | Pakiet propozycji i kryteriów kwalifikacji |
| Polycell | Implementacje komórek według kontraktów projektu | Kandydat implementacji węzła, po walidacji lokalnego kontraktu |

Indeks pokazuje schedulery i executory w kilku projektach. Sam fakt ich obecności
nie uzasadnia uruchomienia wszystkich. Jeden agregat ma mieć jednego
autorytatywnego właściciela wykonania; projektant grafu nie przejmuje tej roli.

## Konkretna mapa uritime

Ścieżki są względne względem korzenia zestawu uritime z indeksu.

| Ścieżka | Symbole z indeksu | Przewidywane zastosowanie |
|---|---|---|
| `uritime/src/urievents/contracts.py` | `ServiceBinding`, `ProcessRef`, `DataRef`, `StreamCheckpoint`, `CommandEnvelope`, `DomainEventEnvelope`, `validate_cqrs_document` | Kontrakty URL/URI/URN/URT i CQRS |
| `uritime/src/uritime/plan_commands.py` | `PlanLedger.propose_plan`, `accept_plan`, `revise_schedule`, `cancel_plan`, `AggregateOwnershipPolicy` | Przyjęcie propozycji i ownership Plan/Schedule |
| `uritime/src/uritime/plan_queries.py` | `PlanQueries.get_plan`, `rebuild_from_events`, `query_knowledge_at` | Projekcje i odczyt historyczny |
| `urt/src/uritime_urt/intents.py` | `validate_ast`, `validate_temporal_intent`, `intent_digest`, `validate_temporal_monitor` | Istniejąca walidacja temporal AST |
| `urt/src/uritime_urt/resolution.py` | `validate_temporal_constraint_graph`, `resolve_temporal_intent`, `revise_plan_anchor_resolution` | Kotwice i zależności czasowe |
| `urt/src/uritime_urt/model.py`, `references.py`, `canonical.py` | `normalize`, `make_schedule`, `to_uri`, `parse_uri`, `canonical_bytes`, `reference_uri` | Kanoniczne deskryptory i tożsamość czasu |
| `uritime/src/uritime/intent_service.py`, `temporal_interpreter.py` | `IntentService.preview`, `interpret_and_record`, `submit_proposal`, `SubLLMModelGateway`, `GatewayTemporalInterpreter` | NL do formalnej propozycji |
| `uritime/src/uritime/temporal_resolver.py`, `temporal_subscriptions.py`, `temporal_monitor.py` | `TemporalConstraintResolver`, `DurableSubscriptionStore`, `DurableTemporalMonitor` | Przyszłe kotwice i ograniczone while/until |
| `uritime/src/uritime/materializer_handoff.py` | `PlanMaterializerHandoff.handoff_occurrence` | Przyjęte occurrence do Autodo |
| `urt/src/uritime_urt/plan_handoff.py`, `autodo.py` | `PlanHandoffController`, `build_plan_handoff_binding`, `DeliveryLedger`, `StoreSink`, `plan_goals` | Wersje planu, fencing, trwałe przekazanie |
| `uritime/src/urievents/data_registry.py` | `DataRegistryPort`, `LocalDataRegistry`, `DataRecord`, `StoredBlob` | URN, treść, wersje i lokalizacje danych |
| `autodo/src/subactor_autonomy/data_pinning.py` | `resolve_and_pin_inputs`, `verify_and_materialize_pinned_inputs`, `build_pure_execution_receipt`, `persist_action_outputs` | Zamrożenie WE/WY dla konkretnego wykonania |
| `autodo/src/subactor_autonomy/operation_descriptor.py` | `canonical_operation_uri`, `build_operation_descriptor`, `descriptor_from_autodo_record`, `descriptor_from_autonom_spec` | Jedna wersjonowana operacja dla transportów |
| `autodo/src/subactor_autonomy/registry.py` | `Registry.describe`, `descriptors`, `resolve_for_execution`, `resolve_historical` | Katalog dostępnych operacji |
| `autodo/src/subactor_autonomy/commands.py`, `queries.py`, `ownership.py` | `handle_command`, `AutodoQueries`, `IntegratedModeAdapter`, `AuthoritativeDispatchGate`, `accept_plan_proposal` | CQRS i ownership Goal/Action |
| `autodo/src/subactor_autonomy/service_binding.py`, `bridge.py` | `normalize_service_binding`, `verify_pinned_binding_compatible`, `ConnectorExecutor`, `UnknownOutcome` | Wiązanie URL i reconciliation skutków |
| `uritime/src/urievents/store.py`, `importers.py`, `export.py` | `UriEventStore`, `SourceEventImporter`, `ResumableUrtExporter`, `to_cloudevents_projection` | Log, inbox, checkpointy i eksport |
| `uritime/src/uritime/planfile_sync.py` | `PlanfileSynchronizer.import_campaign_tickets_idempotent`, `export_urt_planfile_metadata` | Backlog i Planfile |
| `autonom/src/autonom/synthesizer.py`, `subllm_client.py`; Autodo `engine.py`, `llm.py` | `Synthesizer`, `ModelPort`, `SubLLMClient` | Inferencja i kwalifikacja kandydatów |
| `urtlog/src/urtlog/dsl.py`, `registry.py`, `server.py`, `sdk.py` | `UrtEventRecord`, `OperationUri`, `UnifiedRegistry`, `UrtServiceFacade`, `UrtMcpServer`, `build_rest_server`, `UrtClient.span` | Wspólna semantyka przez SDK, REST i MCP |

Podobnie nazwane klasy `SubLLMClient` mają w indeksie różne zestawy metod.
Wspólna nazwa nie oznacza wspólnego API. Również indeksowane fragmenty docstringów
o readonly, idempotency czy fail-closed wymagają potwierdzenia kodem i testem.

## Dokumenty do odczytu na PC przed implementacją adapterów

- `planning/urt-polycell-forge-autonomy.md` — istniejący plan liczący według
  indeksu 707 linii. Jego zawartość nie została załączona.
- `planning/autonomy-pilot/contracts/cells/backlog.reconciliation.cell.yaml`
  oraz `planning/autonomy-pilot/cells/python/backlog_reconciliation.py`.
- `planning/autonomy-pilot/replay.py`: `evaluate_with_polycell`,
  `observation_replay`; `observation_plan.py`: `plan_trigger_history`.
- `uritime/src/urievents/schemas/ur-cqrs-v1.schema.json`.
- Schematy `descriptor-v1`, `temporal-intent-v1`, `temporal-monitor-v1`
  oraz `resolution-v1` w `urt/src/uritime_urt/schemas/`.
- Runtime `urt-record-v1.schema.json` i `urt-record-data-v1.schema.json`.
- `autodo/examples/cqrs-010-operation-descriptors.json`.
- `autodo/docs/CONNECTORS.md`, `RECOVERY-AND-IDENTITY.md`.
- `uritime/planning/CQRS-029-SUBLLM-UPSTREAM.md`.

Istnienie pilota Polycell–uritime oraz planu Forge jest dowodem wcześniejszej
pracy integracyjnej. Nowy adapter powinien się do niej odnieść po odczycie źródeł.
Starszy katalog `urt-records-proposal-0.1.0` nie powinien automatycznie zastąpić
aktualnych schematów runtime.

## Kontrakt przyszłego adaptera

Adapter powinien deklarować projekt i rewizję źródła, nazwę importu, wersję
schematu, mapowanie GraphIR do rzeczywistych pól, tryb `preview` oraz zakres
efektów. Domyślny etap projektowania kończy się artefaktem propozycji. Akceptacja
planu i wykonanie należą do obecnych usług.

Przed dopuszczeniem bindingu trzeba sprawdzić: wymagane pola, wersjonowanie,
powtórzenie z tym samym idempotency key, brak równoległego ownership, zachowanie
po niejednoznacznym wyniku oraz zgodność odczytu projekcji z checkpointem.
Wynik niejednoznacznego wykonania wymaga reconciliation, a nie ślepego ponowienia.

W tej paczce adaptery runtime pozostają **niewdrożone**. Testy indeksowania
potwierdzają tylko parser, ranking i bezwykonaniowy odczyt AST. Nie są testami
działających uritime, Forge, Polycell, SubLLM ani zewnętrznych transportów.
