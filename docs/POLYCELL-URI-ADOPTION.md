# ARP-003: Raport adopcji Polycell i standardów URI (`nl-uri-dsl-llm`)

Data weryfikacji na PC: **2026-11-21**  
Poziom dowodu: **`contract_verified`** — 16/16 testów pozytywnych i negatywnych z [evidence/contract-corpus.json](../evidence/contract-corpus.json) oraz 14/14 przykładów komórki `backlog.reconciliation` przeszło wobec rzeczywistych walidatorów upstream.

## 1. Weryfikacja `wellmanifest/nl-uri-dsl-llm` vs kopia w `heyasa/forge`

Porównanie lokalnych checkoutów (`wellmanifest/nl-uri-dsl-llm@29a67748a41b`, wersja `1.5.0`, oraz `heyasa/forge@e67afb42edb2`):

- **Upstream**: `/home/tom/github/wellmanifest/nl-uri-dsl-llm/schemas/process-uri.schema.json`
- **Kopia w Forge**: `/home/tom/github/paxlet-com/forge/examples/wellman/standards/nl-uri-dsl-llm/process-uri.schema.json`
- **SHA-256 obu plików**: `a18c2f779dfebc9d993ea0e4f011eed62cc33dc4a7d6aeb8cd27d87928e03835`
- **Wynik**: **bajt-w-bajt identyczne** (zero dryfu schematu `ProcessUriSchema`).

## 2. Rzeczywista rozbieżność gramatyk URI w ekosystemie (bez nadpisywania upstream)

Analiza normatywnych schematów na PC wykazała **pięć różnych, celowych profili identyfikatorów** w ekosystemie. ArchPat **nie ujednolica ich na siłę** i nie udaje jednej gramatyki; każdy adapter musi mapować identyfikator do gramatyki właściciela:

| Standard / pakiet | Pole i schemat | Wymagany wzorzec (regex / format) | Przykład poprawny | Przykład odrzucony fail-closed |
|---|---|---|---|---|
| **`wellmanifest/nl-uri-dsl-llm`** | `uri` (`process-uri.schema.json`) | RFC 3986 `format: "uri"` (`scheme://domain/action` lub `urn:...`) | `proc://heyasa.forge/project/impact/v1` | brak pola `uri` (`ValidationError`) |
| **`heyasa/forge` data-plane** | `operation`, `urn` (`process-exchange.schema.json`) | `operation`: `^[a-z][a-z0-9+.-]*://[^\s?#]+$`; `urn`: `^urn:uuid:[0-9a-f-]{36}$` | `urn:uuid:2f65cf6c-f10a-4d82-895b-923779aee001` | niezadeklarowany węzeł w `analyze.impact` |
| **`uritime/uritime` (`urievents`)** | `process.uri`, `inputs[].urn`, `temporal_ref` (`ur-cqrs-v1.schema.json`) | `poaUri`: `^(poa\|urn:poa):[a-z0-9][a-z0-9._:/-]*#(v[0-9]+\|[0-9]+)$`; `temporal_ref` (accepted): `^urt:v1:...$` | `urn:poa:exercise.review#v1`, `urn:sha256:<64hex>` | nieprzypięty `urn:uritime:...` w `decision_mode="accepted"` |
| **`uritime/autodo`** | `uri` (`operation_descriptor.py`) | `canonical_operation_uri()` → `urn:poa:<op_id>#v<version>` (opcjonalnie `op://autonom/.../vN`) | `urn:poa:exercise.review#v1` | `https://example.com/exercise/review` (`Conflict`: URL nie może być dereferencjonowany jako operacja) |
| **`wellmanifest/polycell`** | `urn` (`polycell-cell.schema.v1.json`), `process_ref` (`polycell-plan.schema.v1.json`) | komórka: `^urn:wm:cell:[a-z0-9_-]+:[a-z0-9_.]+:v[0-9]+$`; proces: `^poa://` | `urn:wm:cell:autonomy:backlog.reconciliation:v1`, `poa://shop.local/process/checkout/v1` | `https://not-a-cell-urn.example/bad` (`ValidationError`) |

**Wniosek architektoniczny dla ArchPat (ARP-009):**
- Węzeł w `ArchitectureGraph` nie powinien zakładać jednego regexu dla `process_uri`.
- Profil `uritime`/`autodo` wymaga kanonicznej postaci `urn:poa:<capability>#v<major>` + osobnego `ServiceBinding.url` (SOA URL ≠ POA URI).
- Profil `polycell` używa `urn:wm:cell:<ns>:<name>:v<major>` dla komórek i `poa://...` dla procesów.
- Profil `nl-uri-dsl-llm` / `forge` używa `proc://...` lub `urn:uuid:...` dla zarejestrowanych kontraktów procesowych.

## 3. Weryfikacja `wellmanifest/polycell` (`a50bd58a2656`)

Odczyt lokalnego repozytorium `wellmanifest/polycell` potwierdził jego rzeczywistą rolę:
- **Trzy warstwy**: niezmienny transport (`cellhost.proto`, HTTP, stdio) + generowane interfejsy z YAML (`contracts/cells/*.cell.yaml`) + wymienna logika w jednym pliku (`cells/{python,ts,rust}/`).
- **Standard**: `standard/polycell-cell.schema.v1.json` (`wellmanifest.polycell.cell/v1`, `additionalProperties: false`) oraz `standard/conformance.py` (reguły `PC001`–`PC009`: GAP, ORPHAN, STALE, czystość `[pure]`).
- **Ograniczenie z README Polycell**: równoległe wersje `:v1` i `:v2` tej samej nazwy komórki wymagają jeszcze zmiany generatora ścieżek; standard jest propozycją (`wellmanifest/polycell`).

### Wyniki walidacji korpusu Polycell w pilocie
1. `wellmanifest/polycell/contracts/cells/pricing.quote.cell.yaml` → **PASS** wobec `polycell-cell.schema.v1.json` (`urn:wm:cell:shop:pricing.quote:v1`).
2. `uritime/planning/autonomy-pilot/contracts/cells/backlog.reconciliation.cell.yaml` → **PASS** wobec `polycell-cell.schema.v1.json` (`urn:wm:cell:autonomy:backlog.reconciliation:v1`).
3. Negatywny test niepoprawnego URN (`https://not-a-cell-urn.example/bad`) → **PASS (odrzucony)** przez `Draft202012Validator`.
4. Uruchomienie czystej funkcji `run()` z `uritime/planning/autonomy-pilot/cells/python/backlog_reconciliation.py` na wszystkich przykładach z jej kontraktu YAML → **14/14 PASS**.
