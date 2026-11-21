# Etap 2 (`ARP-004` i `ARP-005`): Wersjonowany IR v2, profile ekosystemu, warstwy i pokrycie user story

Data wdrożenia: **2026-11-21**

## 1. ARP-004 — `archpat.ir/v2` ([src/archpat/ir_v2.py](../src/archpat/ir_v2.py))

Rozszerza `archpat.graph/v1` w sposób w pełni wstecznie kompatybilny:

- **Jawne pochodzenie (`ProvenanceRecord`)**: rozdziela `user_input`, `llm_inference`, `deterministic_rule`, `source_index` oraz `runtime_observation` wraz z poziomem dowodu (`proposed` → `indexed_only` → `source_verified` → `contract_verified` → `integration_verified`).
- **Typowane profile ekosystemu (`ProfileBindings`)** zgodne ze zweryfikowanymi gramatykami z `ARP-002`/`ARP-003`:
  - `uritime`: `poa_uri` (`^(poa|urn:poa):...#(vN|N)$`), `service_url` (`http(s)://`), `temporal_ref` (`urt:v1:...` lub `urn:uuid:...`),
  - `polycell`: `cell_urn` (`^urn:wm:cell:<ns>:<name>:v<major>$`), `process_ref` (`^poa://`), `owner_lang` (`python|ts|rust`), `effects`,
  - `forge`: `process_uri`, `project_urn` (`urn:uuid:...`), `snapshot_id`, `qualification_authority="decision_only"`,
  - `nl_uri`: `action_uri` (RFC 3986), `provenance_source` (`nl_deterministic|llm_gbnf|direct_dsl`),
  - `extensions`: zachowanie nieznanych pól upstream bez cichej utraty.
- **Migracja i deterministyczny hash semantyczny**:
  - `migrate_v1_to_v2()` i `downgrade_v2_to_v1_with_report()` zapewniają bezstratny round-trip dla pól v1 oraz jawny raport pominiętych rozszerzeń v2.
  - `semantic_hash()` liczy deterministyczny SHA-256 niezależny od kolejności węzłów, krawędzi i linków kryteriów.
- **Walidacja (`validate_ir_v2`)**: odrzuca zduplikowane ID, wiszące referencje kryteriów do nieistniejących operacji/węzłów oraz deklaracje `contract_verified`/`integration_verified` pozbawione wpisów `provenance`.

## 2. ARP-005 — Warstwy grafu, pokrycie user story i delta `as-is` → `to-be` ([src/archpat/views_coverage.py](../src/archpat/views_coverage.py))

- **5 jawnych warstw (`extract_view`)** nad wspólnym IR: `domain`, `data_flow`, `deployment`, `temporal`, `implementation`.
- **Raport pokrycia kryteriów akceptacji (`story_coverage_report`)**:
  - Śledzi ścieżki komend (`adapter -> command_handler -> aggregate -> event_store / outbox -> relay -> projector -> read_model`), zapytań (`adapter -> query_handler -> read_model`) i wymagań czasowych (`uritime -> handler`).
  - Usunięcie wymaganego węzła (np. `projector`) daje konkretną diagnozę `gap_detected` (np. `missing_side_effect_free_projector`).
  - Uczciwa granica: poprawna struktura daje `structurally_supported_unverified` (`runtime_verified: false`), dopóki wiązania runtime nie mają dowodu.
- **Delta `as-is` → `to-be` (`as_is_to_be_delta`)**: zestawia indeksy `code2llm` z grafem docelowym (`matched_target_nodes` z `evidence="indexed_only"` vs `new_proposed_nodes`) i jawnie oznacza `unused_proof: false`.

## 3. Nowe polecenia CLI

```bash
archpat migrate build/demo/architecture.json
archpat view build/demo/architecture.json --layer deployment
archpat coverage build/demo/architecture.json
archpat delta build/demo/architecture.json --index examples/indexes/uritime.toon.yaml --index examples/indexes/forge.toon.yaml
archpat schema ir-v2
```
