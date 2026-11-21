# ArchPat 0.1.0

**Architecture Pattern Graph Synthesis** — synteza grafów architektury z user stories, wzorców, ograniczeń i dowodów o istniejących projektach.

Nazwa robocza dystrybucji, importu i CLI: `archpat`. Proponowane miejsce repozytorium: `semcod/archpat`, z adopcją odpowiednich standardów `wellmanifest/*`. Nie opublikowano pakietu ani nie zarezerwowano nazwy w rejestrze. Instaluj z tego katalogu lub dołączonego wheel, nie z niezweryfikowanego `pip install archpat`.

Pełny indeks dokumentacji znajduje się w [docs/README.md](docs/README.md).

## Co działa

- Typowany `StorySpec` i `ArchitectureGraph` z JSON Schema, Pydantic v2 i wielokrawędziowym grafem NetworkX.
- Deterministyczna synteza trzech wariantów CQRS+ES: `modular_monolith`, `worker_split`, `service_split`.
- Twarde ograniczenia RAM, liczby nowych procesów, izolacji projekcji, niezależnego skalowania command/query oraz sprawdzenie deklarowanej pracy offline.
- Jawny ranking, składniki kosztu, zbiór Pareto i diagnostyka odrzuconych wariantów.
- Reguły CQRS, pojedynczego właściciela agregatu, atomowego outbox w jednym logicznym magazynie, idempotencji, replay, checkpointów i ciągłości ścieżek.
- Import obu załączonych indeksów code2llm; wyszukiwanie kandydatów reuse z oznaczeniem `indexed_only`.
- Lokalny `probe` ograniczony do metadanych, SHA-256 i AST; nie importuje ani nie wykonuje sprawdzanego kodu.
- Zestaw wyników: JSON, JSON Schema, GraphML, Mermaid, uzasadnienie decyzji oraz niewysłana propozycja handoff.
- Opcjonalny schemat Protobuf wymiany **własnego IR ArchPat**, bez udawania kontraktu uritime, Forge lub domeny użytkownika.
- Porównanie dwóch grafów ArchPat oraz analiza zależności i propagacji wpływu w modelu.
- LLM → StorySpec przez skonfigurowany endpoint kompatybilny z Chat Completions, np. lokalny Ollama lub LiteLLM. Brak regułowego fallbacku interpretacji języka naturalnego.
- Własne interfejsy shell/CLI, REST i MCP stdio do projektowania i walidacji grafów.

**Istotne granice:** to MVP syntezy z małego katalogu, nie uniwersalny optymalizator dowolnej architektury. RAM i koszt zmian są niezmierzonymi priory. Kryteria akceptacji są zachowane, ale nie są automatycznie dowiedzione. Wynik zawsze ma `execution_ready: false`.

## Szybki start

Python 3.11+; środowisko zweryfikowane w tym wydaniu: Python 3.12. Instalacja pobiera tylko biblioteki Pythona. Nie pobiera modeli LLM ani źródeł innych projektów.

```bash
cd archpat
make install
make test
make demo
```

Lub bez Make:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/archpat synthesize examples/story-local.json \
  --index examples/indexes/uritime.toon.yaml \
  --index examples/indexes/forge.toon.yaml \
  --out build/my-first-architecture
```

`--out` nie nadpisuje niepustego katalogu. `--overwrite` jawnie odświeża wygenerowane pliki. Jeśli ponowny wynik nie ma dopuszczalnego wariantu, wcześniejszy wybrany graf jest usuwany z tego katalogu wynikowego, aby nie pozostawić nieaktualnej rekomendacji.

Wynik `synthesize`:

| Plik | Znaczenie |
|---|---|
| `synthesis.json` | wszystkie warianty, reguły, metryki, przyczyny odrzucenia, ranking |
| `architecture.json` | wybrany graf, operacje, referencje danych i kandydaci reuse |
| `architecture.graphml` | graf z zachowaniem równoległych krawędzi do dalszej analizy |
| `flow.mmd` / `dependencies.mmd` | osobne widoki przepływu i zależności; JSON zachowuje także odpowiedzi |
| `decision.md` | uzasadnienie, założenia, kryteria akceptacji |
| `story.schema.json` / `graph.schema.json` | publiczne schematy własnego IR |
| `architecture.proto` | schemat protobuf IR, gdy żądano formatu protobuf |
| `handoff-proposal.json` | niewysłana propozycja z właścicielami i nierozstrzygniętym czasem |

Kod zakończenia `2` oznacza błąd wejścia, niepoprawny graf lub brak dopuszczalnego wariantu. Samo istnienie poprawnego grafu nie oznacza gotowości systemu do wykonania.

## Warianty zastosowania

```bash
make examples
```

Skrypt porównuje ten sam scenariusz edukacyjny przy czterech zestawach ograniczeń: lokalny, osobny worker, niezależne command/query oraz niewykonalny budżet. Gotowe wyniki są w `examples/generated/`.

Katalog jest celowo zachowawczy: monolit zwykle dominuje w obecnych priory kosztów, dopóki wymaganie izolacji lub niezależnego skalowania nie uzasadni rozdzielenia procesów. Nie modelujemy jeszcze zysku wydajności pod obciążeniem, kosztu awarii ani rzeczywistych opóźnień. Rozbudowę optymalizacji opisuje `docs/DESIGN.md`.

`max_processes` dotyczy **nowych procesów aplikacji**. Istniejące Ollama/SubLLM, uritime, autodo i baza nie są ponownie liczone jako nowe procesy. Ustaw `reserved_ram_mb` na ich zmierzony koszt. Przykładowe 2048 MiB nie jest rekomendacją rozmiaru dowolnego modelu LLM.

## Reuse na Twoim PC

```bash
.venv/bin/archpat index examples/indexes/uritime.toon.yaml --capability temporal
.venv/bin/archpat index examples/indexes/forge.toon.yaml --capability snapshot

.venv/bin/archpat probe examples/indexes/uritime.toon.yaml \
  --root /sciezka/do/uritime --out build/uritime-source-probe.json

.venv/bin/archpat probe examples/indexes/forge.toon.yaml \
  --root /sciezka/do/forge --out build/forge-source-probe.json
```

Indeksy mają rozszerzenie `.yaml`, ale są formatem tekstowym code2llm `M[]/D:`, nie ogólnym manifestem YAML. `probe` nie potwierdza API; rozróżnia brak źródła, obecność pliku, błąd AST i zaobserwowane definicje. Ranking reuse jest leksykalnym wyszukiwaniem po jawnych capability, nie interpretacją user story ani oceną semantycznej zgodności.

Nie ma w tym wydaniu działających runtime adapterów uritime, autodo, Forge, Polycell, nl-uri-dsl-llm, code2schema ani Deconnected. Dokładne punkty integracji i ścieżki źródeł znajdują się w `docs/INTEGRATIONS.md` i `docs/REUSE-FORGE.md`. W indeksie istnieje już `planning/urt-polycell-forge-autonomy.md` oraz `planning/autonomy-pilot/`; trzeba je odczytać przed dopisywaniem równoległych integracji.

## NL → StorySpec przez LLM

```bash
export ARCHPAT_LLM_BASE_URL=http://localhost:11434/v1
export ARCHPAT_LLM_MODEL=nazwa-modelu-juz-dostepnego-lokalnie
# Dla LiteLLM podaj jego root API oraz opcjonalnie ARCHPAT_LLM_API_KEY.

.venv/bin/archpat normalize examples/story.txt --out build/story-from-llm.json
.venv/bin/archpat synthesize build/story-from-llm.json --out build/llm-design
```

Zmienne można przechowywać według `.env.example`, ale program nie ładuje `.env` automatycznie. Model dostaje schemat i opis user story, nie pełne indeksy ani kod Twoich projektów. Są najwyżej dwie próby — pierwotna i naprawa formatu/schematu. Lokalna walidacja nie potwierdza trafności wymagań: sprawdź wywnioskowane operacje i założenia przed użyciem projektu.

Warunki „po zakończeniu”, „przed”, „następny”, „dopóki” pozostają jako `temporal.text` ze statusem `unresolved`. Docelowy adapter przekaże je do istniejącego URT/uritime. ArchPat nie implementuje alternatywnego parsera czasu ani nowej gramatyki URT.

## REST, MCP i shell

Shell jest CLI z argumentami i JSON; nie wykonuje tekstu wygenerowanego przez LLM jako polecenia systemowego.

```bash
make install-api
.venv/bin/archpat serve --host 127.0.0.1 --port 8765
# POST /v1/synthesize — StorySpec JSON
# POST /v1/validate — ArchitectureGraph JSON
# GET /openapi.json — kontrakt wygenerowany z modeli
```

Domyślne API służy do lokalnego użycia. Zdalne uwierzytelnianie i deployment bramy należą do integracji docelowej.

```bash
make install-mcp
.venv/bin/archpat mcp
```

Narzędzia MCP: `architecture_synthesize`, `architecture_validate`, `architecture_diff`, `architecture_impact`. Korzystają z tej samej logiki aplikacji i nie zmieniają źródeł projektów. Konfiguracja klienta MCP powinna wskazywać absolutną ścieżkę do `.venv/bin/archpat`, argument `mcp` i stdio.

## Różnice i wpływ

```bash
.venv/bin/archpat diff examples/generated/local/architecture.json \
  examples/generated/worker/architecture.json --out build/architecture-delta.json
.venv/bin/archpat impact examples/generated/local/architecture.json aggregate.exercise
```

To porównanie dwóch **grafów ArchPat**. Import modeli code2schema/Deconnected i wyznaczenie zmian konkretnych plików są następnym etapem, nie ukrytą funkcją tego polecenia. Wynik nigdy nie przenosi ani nie kasuje kodu.

## Protobuf i zgodność

`contracts/archpat/v1/architecture.proto` opisuje graf ArchPat. Główne węzły i krawędzie mają jawne pola; `story`, `provenance` i `properties` są rozszerzalnymi `google.protobuf.Struct`. To proponowany format wymiany, nie wygenerowana implementacja domeny, API gRPC ani normatywne kontrakty upstream. JSON Schema pozostaje miejscem reguł takich jak dopuszczalne role i identyfikatory.

Nie zmieniaj numerów istniejących pól. Przy wycofaniu rezerwuj numery i nazwy. Docelowy gate `buf breaking` powinien porównywać do ostatniego opublikowanego, przypiętego kontraktu. Konfiguracja Buf jest dołączona; wykonane sprawdzenia są w `evidence/VALIDATION.md`.

## Docker i pakowanie

```bash
make docker-test
make docker-demo
make wheel
```

Budowanie obrazu wymaga sieci dla instalacji bibliotek. Compose uruchamia demo i testy bez sieci zewnętrznej. Optional REST/MCP testy wymagają extras; bazowy obraz sprawdza rdzeń. Stan faktycznie wykonanych kontroli, w tym dostępność Dockera, jest opisany w `evidence/VALIDATION.md`.

## Dokumentacja projektu

- `docs/DESIGN.md` — model docelowy, warstwy grafu, wzorce i funkcja celu.
- `docs/INTEGRATIONS.md` — mapa 20 punktów reuse uritime/URT/autodo.
- `docs/REUSE-FORGE.md` — Forge, Polycell, URI, code2schema i Deconnected.
- `docs/OSS.md` — rekomendacje OSS i zweryfikowane źródła pierwotne.
- `docs/ROADMAP.md` — 15 zadań rozwoju z kryteriami akceptacji.
- `evidence/VALIDATION.md` — zakres, wyniki i granice testów tego wydania.

ArchPat projektuje i wyjaśnia. URT określa znaczenie czasu, uritime posiada Plan/Schedule, autodo posiada Goal/Action i skutki, a Forge kwalifikuje implementację. Taki podział zachowuje istniejące kontrakty i ogranicza liczbę równoległych mechanizmów wymagających późniejszego scalania.
