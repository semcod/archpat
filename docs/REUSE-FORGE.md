# Reuse: Forge, Polycell i kontrakty URI

Stan analizy: **21 listopada 2026**. Pakiet i robocza nazwa dystrybucji: `archpat`. Proponowane miejsce repozytorium: `semcod/archpat`; przyjmowane standardy: właściwe pakiety `wellmanifest/*`. To propozycja, nie utworzone repozytorium ani opublikowana dystrybucja. Profil organizacji WellManifest rozróżnia właściciela repozytorium (`HOME`) od stosowanych standardów (`ADOPT`) i umieszcza uruchamiane narzędzia w organizacjach produktowych.

## Wniosek

Archpat powinien być właścicielem **modelu architektury docelowej, wariantów, dopasowania do user story i uzasadnienia wyboru**. Forge ma już wiele elementów potrzebnych do analizy stanu istniejącego, wyszukiwania reuse, utrwalania snapshotów i kwalifikacji zmian. Należy połączyć te odpowiedzialności adapterami zamiast powielać ich implementacje.

Model docelowy może zawierać nowy komponent, którego kod jeszcze nie istnieje. Taki węzeł musi mieć status propozycji. Powiązanie go z istniejącym modułem wymaga osobnego dowodu: ścieżki, symbolu, rewizji i zgodności kontraktu. Podobieństwo nazwy lub sugestia LLM nie są tym dowodem.

## Jak mocne są dostępne dowody

Załącznik `map.toon(3).yaml` jest indeksem `code2llm`, a nie archiwum kodu Forge. Nagłówek podaje 574 pliki, w tym 55 plików Python, oraz 525 funkcji i 46 klas. Indeks zawiera ścieżki i nazwy symboli, czasem skrócone informacje o argumentach. Nie zawiera treści implementacji, modeli żądań, zawartości schematów, wersji dystrybucji ani wyników uruchomionych tutaj testów.

W poniższej tabeli **symbol zaobserwowany** oznacza wyłącznie obecność w indeksie. **Proponowane użycie** jest projektem integracji. Żaden wiersz nie stanowi deklaracji, że adapter został uruchomiony z kodem znajdującym się na PC użytkownika.

## Mapa Forge do ponownego użycia

Wszystkie ścieżki w tej tabeli są względne wobec katalogu głównego Forge.

| Obszar | Ścieżka i zaobserwowane symbole | Proponowane użycie w Archpat | Co sprawdzić lokalnie |
|---|---|---|---|
| Katalog | `packages/forge_base/forge_base/catalog.py`: `Catalog.resolve`, `list`, `upsert`, `upsert_batch`, `export_snapshot`, `import_snapshot`; `validate_entry`, `process_schema_digest` | Powiązanie węzłów docelowych z rzeczywistymi procesami, usługami i zasobami | Typy wpisów, klucze tożsamości, wersjonowanie i konflikt aktualizacji |
| Graf kodu | `packages/forge_base/forge_base/semcod.py`: `load_projection`, `graph_from_analysis`, `analyze_project_graph`, `load_graph`, `validate_graph` | Dostawca grafu stanu istniejącego i dowodów o zależnościach | Schemat grafu, znaczenie krawędzi, obsługa brakujących danych |
| Analiza snapshotu | `packages/forge_base/forge_base/analysis.py`: `analyze_snapshot` | Analiza raz dla konkretnego snapshotu, reuse przy porównaniu wielu wariantów | Format wejścia i wyniku, identyfikacja analizatora i cache |
| Snapshoty | `packages/forge_base/forge_base/snapshots.py`: `SnapshotStore.capture`, `verify`, `manifest`, `materialize`, `verify_workspace` | Powtarzalne wejście do syntezy i kwalifikacji refaktoryzacji | Tożsamość snapshotu, czysty/brudny checkout, zakres plików i hash |
| Wyszukiwanie reuse | `packages/forge_base/forge_base/reuse.py`: `ReuseIndex.update`, `suggest`, `read_fragment` | Lista kandydatów implementacyjnych dla wymaganej zdolności | Model cech, scoring, zakres danych, dowody zgodności kontraktów |
| Kontrakty procesów | `packages/forge_base/forge_base/contracts.py`: `processes`, `resolve`, `validate_input` | Sprawdzenie konkretnego process URI i DTO, gdy graf otrzymuje binding | Faktyczny rejestr URI, błędy walidacji i efekty operacji |
| Wywołania operacji | `packages/forge_base/forge_base/operations.py`: `operations`, `resolve`, `call`, `validate_registry` | Późniejsze przekazanie zatwierdzonego planu do istniejącego runtime | Idempotencja, autoryzacja, statusy i format receipt |
| Cykl kandydata | `packages/forge_base/forge_base/manager.py`: `Manager.stage`, `validate`, `promote`, `rollback`, `baseline_bundle`, `analyze_snapshot`, `invoke`, `evolve_once` | Zachowanie Forge jako właściciela stagingu i kwalifikacji implementacji | Format bundle, warunki kwalifikacji, tożsamość środowiska |
| Zadania refaktoryzacji | `packages/forge_base/forge_base/project_jobs.py`: `prepare`, `run_checks`, `publish_precondition`, `tree_digest` | Izolowana zmiana i sprawdzenie planu migracji wygenerowanego przez Archpat | Ograniczenia ścieżek, format patcha, preconditions i publikacja |
| Dostawca LLM Forge | `packages/forge_base/forge_base/providers.py`: `ProviderConfig`, `ProviderClient.propose`, `validate_bundle` | Integracja tylko przez jawne mapowanie odpowiedzi architektonicznej na kontrakt Forge | Schemat bundle; nie zakładać, że jest równy modelowi Archpat |
| SubLLM | `packages/forge_base/forge_base/subllm_adapter.py`: `SubLLMConfig.from_env`, `validate`, `SubLLMProvider.propose` | Reuse centralnego routingu i konfiguracji modeli przez cienki adapter | Faktyczne API, timeouty, budżety, format usage i błędów |
| Tożsamość wykonania | `packages/forge_base/forge_base/runtime.py`: `describe_runtime`, `validate_runtime`, `execution_identity`, `lock_digest` | Przypięcie oceny wykonalności do konkretnego środowiska | Czy kontrakt obejmuje interpreter, zależności i obraz kontenera |
| Kwalifikacja | `packages/forge_base/forge_base/validation.py`: `profile_digest`, `reference_impact`, `check_result`, `qualify`, `paired_benchmark` | Reuse istniejącej kwalifikacji implementacji; dodatkowe reguły architektury pozostają osobne | Pokrywane warunki; sama nazwa `qualify` nie dowodzi weryfikacji CQRS/ES |
| REST i MCP | `packages/forge_base/forge_base/api.py`: `create_app`; `mcp_server.py`: `process_catalog`, `invoke_checked`, `catalog_query`, `create_mcp`, `run_mcp` | Jedna semantyka procesu dostępna z wielu interfejsów | DTO, tryby transportu, limity, błędy i zgodność odpowiedzi |
| Most Wellman | `packages/forge_wellman/forge_wellman/bridge.py`: `register`, `resource_reference`, `resource_urn`, `_native_contracts`, `_binding`, `_verify_pins` | Reuse obecnego mapowania standardów i identyfikatorów zasobów | Publiczne wejścia mostu, przypięte rewizje i wersje schematów |

Nie należy bezpośrednio wiązać Archpat z symbolami zaczynającymi się od `_`. Są wskazówką miejsca implementacji; adapter powinien wykorzystywać potwierdzone publiczne wejście albo mały nowy publiczny kontrakt dodany w repozytorium właściciela.

## Schematy, które indeks rzeczywiście wymienia

Poniższe pliki są dobrym pierwszym celem lokalnego przeglądu. Ich zawartości nie było w załączniku:

- `examples/wellman/standards/nl-uri-dsl-llm/process-uri.schema.json`;
- `examples/wellman/standards/data-plane/process-exchange.schema.json`;
- `examples/wellman/standards/data-plane/resource-reference.schema.json`;
- `examples/wellman/standards/authority-lifecycle/authority-lifecycle.schema.json`;
- `examples/wellman/standards/project-ssot/project-ssot.schema.json`;
- `examples/wellman/standards/validation-attestation/validation-attestation.schema.json`;
- `examples/tasks/task.schema.json`;
- `examples/snapshots/manifest.schema.json`;
- `examples/cache/execution-identity.schema.json`;
- `packages/forge_wellman/forge_wellman/upstream-pins.json`.

Przy wiązaniu pakietów zapisać: URL repozytorium, commit, ścieżkę kontraktu, hash pliku, wersję schematu i wynik testu zgodności. Brak tych danych powinien dawać status `unverified`, a nie automatyczny wynik pozytywny.

## Polycell: uwzględnienie bez wymyślania kontraktu

Adres wskazany przez użytkownika: <https://github.com/wellmanifest/polycell>.

Odczyt przez narzędzie internetowe zakończył się `DisabledError`. Nie jest to dowód, że repozytorium nie istnieje lub jest prywatne. Wyszukiwanie nie dostarczyło treści normatywnych. Dlatego obecna propozycja **nie deklaruje zgodności z Polycell, jego licencji, API ani znaczenia pojęcia cell**.

Punkt rozszerzenia w Archpat powinien przyjmować przypięty profil wzorców i ograniczeń. Po lokalnym odczycie Polycell należy ustalić, czy dostarcza on model jednostki architektury, reguły składania, kontrakty portów, model wdrożenia czy inny zakres. Dopiero wtedy mapować jego pojęcia na węzły i krawędzie IR. Nazwa adaptera, np. `PolycellProfileProvider`, byłaby własnym kontraktem Archpat, nie zaobserwowanym API Polycell.

Kryterium ukończenia integracji: rzeczywisty przykład z repozytorium Polycell przechodzi walidację właściciela, import do Archpat i ponowny eksport bez utraty normatywnych informacji. Nieznane pola muszą pozostać w rozszerzeniach lub spowodować czytelny błąd.

## nl-uri-dsl-llm: znaczenie URI i granica NL

Adres wskazany przez użytkownika: <https://github.com/wellmanifest/nl-uri-dsl-llm>.

Odczyt również zakończył się `DisabledError`. Indeks Forge potwierdza obecność lokalnej kopii `process-uri.schema.json`, ale nie pozwala odtworzyć jej gramatyki. Nie należy uznawać przykładowych identyfikatorów nowej paczki za URI zgodne ze standardem bez tego sprawdzenia.

Proponowany przepływ: opis naturalny → propozycja typowanego wymagania → model Archpat → rozstrzygnięcie bindingów do zarejestrowanych procesów → walidacja rzeczywistego schematu URI. LLM może sugerować zdolność i operację; nie tworzy automatycznie istniejącej implementacji ani rejestracji procesu.

W nomenklaturze projektu:

| Oznaczenie | Rola | Przykład informacji, nie gotowego API |
|---|---|---|
| URL | Adres usługi / SOA | Endpoint konkretnego wdrożenia |
| URI | Identyfikator operacji / POA | Zarejestrowana komenda lub zapytanie |
| URN | Tożsamość danych wejścia/wyjścia | Wersjonowany artefakt lub zasób |
| URT | Czas i relacje temporalne | Intencja czasu, kotwica, okno, deadline |

Technicznie URL i URN są rodzajami URI; tabela określa role w ekosystemie użytkownika, nie rozłączne klasy standardu internetowego. Protobuf jest formatem schematu i serializacji; REST, MCP i shell są sposobami dostępu. Nie należy przedstawiać ich jako konkurencyjnych wzorców architektury.

## Sąsiednie projekty: as-is przed to-be

### code2schema

Oficjalny opis pakietu deklaruje przejście od kodu Python przez AST i klasyfikację CQRS do grafu wywołań, modelu zdarzeń, workflow DAG oraz JSON, Protobuf, Markdown, GraphML i DOT. Pełny DFG widnieje w roadmapie. To źródło hipotez i struktur o istniejącym kodzie; statyczna klasyfikacja nie dowodzi semantycznej poprawności komend i zapytań.

Źródło: <https://pypi.org/project/code2schema/0.1.9/>. We wcześniejszym opisie 0.1.7 udokumentowano `extract_project`, `analyze`, `build_rich_graph`, `infer_event_model`, `to_proto` i `to_markdown`: <https://pypi.org/project/code2schema/0.1.7/>. Publiczne API trzeba sprawdzić dla konkretnej lokalnej wersji. Opis 0.1.9 zawiera rozbieżne wzmianki o licencji MIT i Apache-2.0, dlatego decyzję o reuse oprzeć na pliku licencji przypiętej rewizji.

Archpat powinien importować jego IR i dowody, a istniejące generatory wykorzystać tam, gdzie zapewniają wymagane zachowanie. Własny eksport roboczego IR nie jest deklaracją pełnej kompatybilności z generatorem code2schema ani ze standardami upstream.

### Deconnected

Oficjalna strona opisuje graf dowodów obejmujący frontend, trasy API, backend, workerów, Docker i SQL, z użyciem m.in. LibCST i sqlglot, importem topologii TestQL, analizą granic ekstrakcji oraz planami refaktoryzacji. Strona opisuje narzędzie jako eksperymentalne. Źródło: <https://pypi.org/project/deconnected/>.

Rekomendowany podział: Deconnected dostarcza obecne zależności i kandydatów granic, Archpat określa docelowe granice wynikające z user story, a Forge kwalifikuje konkretną zmianę. Nie uruchamiać równolegle dwóch niezależnych wykonawców patchy dla tego samego planu. Nie uznawać braku statycznej referencji za dowód, że moduł można usunąć.

## Podział odpowiedzialności całego przebiegu

| Właściciel | Odpowiedzialność |
|---|---|
| Archpat | Wymagania, warianty grafu docelowego, ograniczenia, ocena, decyzja, plan różnic |
| URT | Semantyka odniesień czasowych |
| uritime | Plan i harmonogram |
| autodo | Cel, wykonanie i receipts |
| autonom / SubLLM | Synteza propozycji i dostęp do modeli zgodnie z istniejącymi kontraktami |
| Forge | Snapshot, reuse, staging, kwalifikacja, wdrożenie kandydata i rollback |
| Wellman | Sprawdzone mapowanie przyjmowanych standardów |

W modelu rozdzielić graf projektu, graf wykonania i fakty o wykonaniu. Planowana krawędź z czasem przyszłym nie jest zdarzeniem domenowym, które już zaszło. Dokument decyzji architektonicznej nie jest potwierdzeniem skutków działania.

## Istniejący plan integracji

Drugi załącznik, indeks uritime, wymienia `planning/urt-polycell-forge-autonomy.md` oraz pliki w `planning/autonomy-pilot/`. Oznacza to istnienie wcześniejszego miejsca planowania tego powiązania. Treści tych plików nie ma w indeksie. Przed utworzeniem nowych ticketów należy odczytać je lokalnie i przypisać zadania z `ROADMAP.md` do istniejących pozycji, rozszerzając ich kryteria tam, gdzie zakres się pokrywa. Nie tworzyć drugiego niezależnego planu autonomii ani nie nadpisywać poprzednich ustaleń.

## Dodatkowe źródła koncepcyjne

- Katalog organizacji i zasady wersjonowania kontraktów: <https://github.com/wellmanifest>.
- Rola LLM jako dostawcy propozycji oraz zachowanie pochodzenia danych: <https://github.com/wellmanifest/wellm/blob/main/docs/LLM.md>.
- Konkretny proces, rejestracja i oddzielenie wzorca uprawnień od wywołania w projekcie wellm: <https://github.com/wellmanifest/wellm/blob/main/docs/URI_PROCESS.md>.

Te materiały wspierają kierunek projektu, ale nie zastępują niedostępnych kontraktów Polycell i nl-uri-dsl-llm. Nie traktować indeksu, strony opisu pakietu ani wyniku wyszukiwania jako wykonanego testu integracji.
