# ArchPat: dobór OSS i granice syntezy architektury

Stan analizy: 21 listopada 2026 r.

## Rekomendacja

ArchPat ma być paczką Python do syntezy i oceny grafów architektury uwzględniających user stories, wzorce, przepływy danych oraz ograniczenia środowiska. Najmniejszy użyteczny rdzeń to **Pydantic + NetworkX + wersjonowany katalog wariantów + deterministyczne reguły walidacji**. LLM pomaga zamienić opis potrzeby na ustrukturyzowane wymagania i proponuje rozwiązania; decyzja o ich dopuszczeniu pozostaje jawna i odtwarzalna.

**Zakres MVP** obejmuje modele Pydantic, grafy NetworkX, trzy katalogowe warianty architektury i deterministyczną walidację. **OR-Tools, Z3, CALM i Structurizr są kierunkami rozbudowy, a nie obietnicą funkcji zaimplementowanych w MVP.** Dokument opisuje również docelowe integracje; ich obecność w tabeli nie oznacza, że są zainstalowane, uruchomione lub przetestowane.

Rekomendowany podział własności: implementacja runtime w docelowym `semcod/archpat`; opcjonalny domain pack ze standardami i regułami w ekosystemie `wellmanifest`. Nazwa dystrybucji, importu i CLI w przygotowanej paczce to `archpat`. To propozycja organizacyjna, nie twierdzenie o utworzeniu repozytorium ani publikacji na PyPI. Kontekst organizacji należy weryfikować w [oficjalnym profilu wellmanifest](https://github.com/wellmanifest).

## Co wykorzystać i do czego

| Projekt / standard | Wartość dla ArchPat | Miejsce w rozwiązaniu |
|---|---|---|
| [Pydantic](https://github.com/pydantic/pydantic) | Typowane wymagania, wzorce, elementy grafu, raporty; generowanie JSON Schema i walidacja danych | Rdzeń MVP |
| [NetworkX](https://networkx.org/documentation/stable/) | Grafy skierowane z wieloma krawędziami, osiągalność, cykle, analiza wpływu zmian | Rdzeń MVP |
| [CALM — FINOS](https://github.com/finos/calm-schema) | Maszynowy model architektury, przepływy, interfejsy i wzorce opisane ograniczeniami | Docelowy eksport i walidacja wymiany |
| [Structurizr DSL](https://docs.structurizr.com/dsl) | Kilka widoków C4 z jednego tekstowego modelu architektury | Docelowy eksporter widoków |
| [OR-Tools CP-SAT](https://developers.google.com/optimization/cp/cp_solver) | Dobór komponentów, rozmieszczenia i wariantów przy ograniczeniach całkowitoliczbowych | Opcjonalny przyszły solver |
| [Z3](https://github.com/Z3Prover/z3) | Bogate niezmienniki logiczne, teorie arytmetyczne, sprawdzanie sprzeczności | Alternatywa dla szczególnych klas reguł |
| [PydanticAI](https://github.com/pydantic/pydantic-ai) | Walidowane wyjście LLM; tryby native, tool i prompted output | Opcjonalny adapter, gdy istniejący subllm nie pokryje potrzeby |
| [Import Linter](https://github.com/seddonym/import-linter) i [Grimp](https://github.com/seddonym/grimp) | Kontrola importów, kierunku zależności oraz niezależności modułów | Narzędzia rozwoju i CI, zgodność implementacji z modelem |
| [Buf CLI](https://github.com/bufbuild/buf) | Lint, kompilacja i kontrola zgodności zmian schematów Protobuf | Docelowa bramka kontraktów |
| [OpenAPI](https://spec.openapis.org/oas/latest.html) | Opis kontraktów HTTP | Docelowa projekcja tego samego modelu operacji |
| [AsyncAPI](https://www.asyncapi.com/docs/reference/specification/v3.0.0) | Opis komunikacji wiadomościami i zdarzeniami, kanałów oraz operacji | Docelowa projekcja przepływów wiadomości |
| [eventsourcing](https://eventsourcing.readthedocs.io/en/stable/topics/application.html) | Event store, aplikacje, snapshoty i notification log | Referencja lub opcjonalny backend; najpierw reuse istniejącego autodo |
| [LangGraph](https://github.com/langchain-ai/langgraph) | Trwała orkiestracja długich, stanowych przepływów agentowych | Opcjonalny adapter, bez dublowania uritime/autodo |

NetworkX jest pakietem czysto pythonowym bez obowiązkowych zależności zewnętrznych; wybrane funkcje wymagają dodatkowego stosu naukowego. Nie trzeba instalować całego tego stosu dla podstawowego `MultiDiGraph`, osiągalności i wykrywania cykli. Źródło: [instalacja NetworkX](https://networkx.org/documentation/stable/install.html).

PydanticAI zapewnia walidację wyjścia określonego modelem Pydantic, ale nie należy utożsamiać każdej formy jego wyjścia strukturalnego z pełną walidacją. Dokumentacja `StructuredDict` wskazuje, że przy przekazaniu samego schematu wynikowy słownik wymaga dodatkowej walidacji. Dla ArchPat preferowany jest konkretny model Pydantic, po nim reguły semantyczne grafu. Źródło: [PydanticAI — output](https://github.com/pydantic/pydantic-ai/blob/main/docs/output.md).

## CALM: najbliższy standard modelu architektury

CALM, czyli Common Architecture Language Model, opisuje architekturę jako dane: węzły, relacje, interfejsy, przepływy biznesowe i kontrole. Projekt rozróżnia instancję architektury, wzorzec będący schematem ograniczeń oraz historię kolejnych modeli. To odpowiada potrzebie modelowania wzorców i przepływów znacznie lepiej niż sam zestaw strzałek na diagramie.

Wzorzec CALM może określać, jakie węzły i połączenia muszą wystąpić oraz jakie właściwości muszą mieć. Nie oznacza to automatycznej syntezy globalnie optymalnego rozwiązania. Oficjalne repozytorium opisuje CALM AI jako narzędzia promptowe; nie należy przypisywać im roli zweryfikowanego solvera architektury.

Docelowa integracja ArchPat powinna:

1. Zachować własny model IR z wymaganiami, identyfikatorami URL/URI/URN/URT, powiązaniem z user stories i pochodzeniem dowodów.
2. Eksportować podzbiór modelu do **przypiętej wersji** CALM.
3. Walidować wynik rzeczywistym schematem CALM.
4. Jawnie wymieniać informacje, których format wymiany nie przenosi bez rozszerzeń.
5. Trzymać model decyzyjny i estymacje kosztów poza diagramem prezentacyjnym.

Wygenerowanie JSON o podobnych polach nie wystarcza, aby deklarować zgodność CALM. Tak samo eksport Mermaid lub C4 nie dowodzi poprawności semantycznej architektury.

Źródła: [CALM schema](https://github.com/finos/calm-schema), [Architecture as Code](https://github.com/finos/architecture-as-code), [oficjalne wprowadzenie do CALM](https://github.com/finos/architecture-as-code/blob/main/docs/docs/tutorials/_calm-overview/01-what-is-calm.mdx), [standardy i dekoratory CALM](https://github.com/finos/architecture-as-code/blob/main/calm/draft/2026-03/standards/README.md).

## Co oznacza optymalność

Architektura jest oceniana względem określonych wymagań, kandydatów i modelu kosztów. Nie ma podstaw, by skończony katalog nazwać przeszukaniem wszystkich możliwych architektur.

Rzetelny komunikat MVP brzmi na przykład:

> Najlepszy z trzech katalogowych wariantów, które przeszły zadane reguły, według jawnego rankingu. Wynik jest rekomendacją modelową; wartości RAM i latencji nie są pomiarami.

Docelowy solver może wzmocnić tę gwarancję, lecz tylko w granicach formalnego modelu. Zapis wyniku powinien rozróżniać zakres przeszukiwania, wykonalność, ocenę rankingu, status solvera i jakość estymacji.

Przykładowy **projekt kontraktu przyszłego solvera**, nie API OR-Tools ani funkcja deklarowana w MVP:

```json
{
  "search_scope": "catalog_candidates",
  "candidate_count": 18,
  "status": "FEASIBLE",
  "objective_definition": "weighted_cost_v1",
  "objective_value": 147,
  "best_bound": 128,
  "time_limit_seconds": 5,
  "assumptions": ["RAM estimates are unmeasured"],
  "infeasible_constraints": []
}
```

### Twarde ograniczenia i miękkie kryteria

Twarde ograniczenia decydują o dopuszczalności: wymagany tryb offline, dostępna liczba maszyn, wymagane interfejsy, brak zapisu przez query path, odtwarzalny zapis zdarzeń przy ES. Budżet RAM może być twardym ograniczeniem modelowym, ale tylko przy jawnie oznaczonych założeniach o zużyciu pamięci; sam szacunek nie dowodzi, że system zmieści się w pamięci na komputerze użytkownika.

Miękkie kryteria porządkują dopuszczalne warianty: koszt implementacji, koszt migracji, liczba procesów, estymowana latencja, stopień reuse i przewidywany narzut operacyjny. Wagi muszą być zapisane wraz z wynikiem. Gdy warianty wymieniają RAM na opóźnienie albo prostotę na izolację, pomocny jest zbiór Pareto zamiast ukrywania decyzji w jednej liczbie.

Jeżeli nic nie spełnia ograniczeń, narzędzie powinno zwrócić przyczyny i propozycje zmian. Nie powinno bez wiedzy użytkownika osłabiać ograniczeń, aby zawsze mieć „zwycięzcę”.

### CP-SAT i Z3

CP-SAT jest dobrym kandydatem dla wyboru dyskretnych wariantów, zasobów i rozmieszczenia. Model używa zmiennych i współczynników całkowitoliczbowych; wartości ułamkowe wymagają świadomego skalowania. Solver rozróżnia `OPTIMAL`, `FEASIBLE`, `INFEASIBLE`, `MODEL_INVALID` i `UNKNOWN`. Limit czasu może zakończyć pracę bez dowodu optymalności albo nawet bez znalezienia rozwiązania, choć rozwiązanie istnieje.

Dokumentacja OR-Tools zaznacza dodatkowo, że `OPTIMAL` może oznaczać rozwiązanie problemu samej wykonalności lub zakończenie w ramach określonej tolerancji luki. ArchPat musi zapisać parametry solvera i definicję problemu, zanim przetłumaczy ten status na komunikat dla użytkownika.

Z3 jest solverem SMT: nadaje się do bogatszych zależności logicznych i teorii arytmetycznych. Nie jest automatycznie szybszym zamiennikiem CP-SAT. Nie warto instalować obu na początku, jeśli problem sprowadza się do wyboru spośród trzech wariantów i prostych reguł.

Źródła: [CP-SAT](https://developers.google.com/optimization/cp/cp_solver), [limity solvera](https://developers.google.com/optimization/cp/cp_tasks), [statusy i rozwiązywanie problemów OR-Tools](https://github.com/google/or-tools/blob/stable/ortools/sat/docs/troubleshooting.md), [optymalizacja w Z3](https://microsoft.github.io/z3guide/docs/optimization/arithmeticaloptimization/), [Programming Z3](https://z3prover.github.io/papers/programmingz3.html).

## Zasady modelowania ograniczające refaktoryzację

Poniższe punkty są rekomendacjami projektowymi dla ArchPat, a nie opisem automatycznych gwarancji powyższych bibliotek.

1. **Jeden model operacji, wiele adapterów.** REST, MCP i shell powinny odwoływać się do tej samej operacji domenowej i tych samych kontraktów wejścia/wyjścia.
2. **Semantyka oddzielona od sposobu dostępu.** `command`, `query` i `event` opisują znaczenie; HTTP, MCP i CLI opisują interfejs lub komunikację. Protobuf opisuje kontrakt wiadomości i serializację. Nie należy łączyć tych pojęć w jeden enum `api_type`.
3. **CQRS nie wymusza mikroserwisów.** Rozdzielenie command/query można zrealizować w modularnym monolicie. Osobne procesy i bazy wymagają uzasadnienia wymaganiami.
4. **ES wymaga czegoś więcej niż logowania.** Model musi wskazywać trwałe zdarzenia, właściciela zapisu, porządek w strumieniu, wersje, odtwarzanie i sposób tworzenia projekcji.
5. **Kilka warstw grafu.** Graf importów, wywołań, danych, zdarzeń, relacji czasowych i wdrożenia powinien mieć rozróżnione typy relacji. Cykl importów i kontrolowana pętla procesu biznesowego nie są tym samym problemem.
6. **Stabilne identyfikatory i wersje.** Tożsamość operacji, schematu danych i węzła nie powinna wynikać wyłącznie z aktualnej ścieżki pliku.
7. **Traceability.** Każdy element proponowanej architektury powinien mieć uzasadnienie w user story, ograniczeniu, wzorcu albo zidentyfikowanym obowiązku infrastrukturalnym.
8. **Baseline, target i delta.** Plan migracji powinien pokazać, co zachować, przenieść, osłonić adapterem, zastąpić lub wygasić. Generowanie dużego nowego repo nie zastępuje bezpiecznej migracji.
9. **Pochodzenie wiedzy.** Indeks kodu dowodzi obecności nazw i relacji rozpoznanych przez indeksator, a nie zgodności API. Weryfikacja kodu, schematu, importu i kontraktu testowego to osobne poziomy dowodu.
10. **URT jako integracja domenowa.** Znaczenia czasu z uritime należy zachować przez adapter i deklarowany kontrakt. Zapisanie pola `urt` nie daje automatycznie zgodności z istniejącą implementacją.

Model wyjściowy LLM powinien przejść kolejno: walidację struktury, walidację referencji w grafie, reguły wzorców, sprawdzenie ograniczeń i ocenę pokrycia wymagań. Dopiero później można przekazać plan do narzędzi generujących lub zmieniających kod.

## Kontrakty i bramki zgodności

### Protobuf i Buf

Buf rozróżnia zgodność generowanego kodu na poziomie plików (`FILE`), pakietów (`PACKAGE`), wire plus JSON (`WIRE_JSON`) i samego binarnego wire (`WIRE`). Przejście łagodniejszej kontroli nie oznacza zgodności na wszystkich poziomach.

Przy usuwaniu pól Protobuf należy zachować rezerwacje numerów, a odpowiednio również nazw. Numer pola jest elementem formatu danych; odzyskanie go dla innego znaczenia jest niebezpieczne. Nowy generator ArchPat nie powinien przy każdym przebiegu numerować pól na nowo według kolejności na liście.

Źródła: [Buf — wykrywanie zmian niezgodnych](https://buf.build/docs/breaking/), [konfiguracja Buf](https://buf.build/docs/configuration/), [Protobuf proto3 — usuwanie i aktualizacja pól](https://protobuf.dev/programming-guides/proto3/).

### HTTP i wiadomości

OpenAPI opisuje interfejsy HTTP. AsyncAPI opisuje interfejsy komunikacji wiadomościami, kanały, operacje i powiązania protokołów. Żaden z tych formatów sam nie określa kompletnej architektury aplikacji. Dla ArchPat oba powinny być projekcjami wspólnego modelu, z jawnym mapowaniem identyfikatorów operacji i schematów.

AsyncAPI nie zakłada konkretnej topologii lub wzorca. Nie należy automatycznie utożsamiać jego obecności z koniecznością uruchomienia brokera. Źródła: [OpenAPI](https://spec.openapis.org/oas/latest.html), [AsyncAPI 3.0.0](https://www.asyncapi.com/docs/reference/specification/v3.0.0).

### Architektura wykonana w kodzie

Import Linter pozwala egzekwować zakazane importy, warstwy i niezależność modułów. Jest dobrym uzupełnieniem planu refaktoryzacji: deklaracja granicy w grafie może prowadzić do konkretnej reguły w CI. Nie wykrywa wszystkich zależności dynamicznych i nie zastępuje testów zachowania.

Docelowe bramki: walidacja IR, spójność referencji, pokrycie user stories, kontrola importów, zgodność kontraktów Protobuf/HTTP, test odtwarzania projekcji ES oraz test migracji danych. Dla integracji z forge/autodo obowiązuje dodatkowo test mapowania na rzeczywisty kontrakt ich lokalnej wersji.

Źródła: [Import Linter](https://github.com/seddonym/import-linter), [kontrakty Import Linter](https://import-linter.readthedocs.io/en/stable/contract_types/), [warstwy](https://import-linter.readthedocs.io/en/stable/contract_types/layers/) i [niezależność](https://import-linter.readthedocs.io/en/stable/contract_types/independence/). Składnię konfiguracji należy sprawdzić względem przypiętej wersji narzędzia.

## Licencje zweryfikowanych składników

| Składnik | Licencja wskazana przez projekt | Źródło |
|---|---|---|
| Pydantic | MIT | [LICENSE](https://github.com/pydantic/pydantic/blob/main/LICENSE) |
| PydanticAI | MIT | [pyproject.toml](https://github.com/pydantic/pydantic-ai/blob/main/pyproject.toml) |
| NetworkX | BSD-3-Clause | [repozytorium](https://github.com/networkx/networkx) |
| CALM schema | Apache-2.0 | [repozytorium](https://github.com/finos/calm-schema) |
| Structurizr | Apache-2.0 | [LICENSE](https://github.com/structurizr/structurizr/blob/main/LICENSE) |
| OR-Tools | Apache-2.0 | [repozytorium](https://github.com/google/or-tools) |
| Z3 | MIT | [repozytorium](https://github.com/Z3Prover/z3) |
| Import Linter | BSD-2-Clause | [LICENSE](https://github.com/seddonym/import-linter/blob/main/LICENSE) |
| Buf CLI | Apache-2.0 | [repozytorium](https://github.com/bufbuild/buf) |

Weryfikacja dotyczy wskazanych projektów. Nie wykonano pełnego audytu zależności tranzytywnych ani usług komercyjnych dostępnych pod tymi samymi markami. Nie utożsamiać licencji Buf CLI z warunkami hostowanego registry ani licencji bibliotek Structurizr z dowolną ofertą usługową. Licencje Grimp, eventsourcing i LangGraph należy osobno przypiąć i odczytać przed ich dołączeniem do dystrybucji; nie są konieczne dla obecnego MVP.

## Nazwa ArchPat

**ArchPat — pattern-aware architecture graph synthesis** odpowiada funkcji paczki: architektura, wzorce i synteza grafu. Dwa wyszukiwania, w tym w silniejszym silniku, nie wykazały oczywistego projektu Python o identyfikatorze `archpat`. Bezpośredni odczyt stron PyPI był zablokowany przez narzędzie wyszukiwania, więc nie potwierdzono dostępności nazwy w rejestrze. Przed publikacją potrzebna jest ponowna kontrola; paczka lokalna nie wymaga rezerwacji nazwy na PyPI.

Rozważane alternatywy mają widoczne kolizje:

| Nazwa | Przykład istniejącego użycia |
|---|---|
| `archspec` | [Pakiet PyPI](https://pypi.org/project/archspec/) do charakterystyk architektury systemu i CPU |
| `archgraph` | [Pakiet PyPI](https://pypi.org/project/archgraph/) do analizy kodu i grafów |
| `patternforge` | [Pakiet PyPI](https://pypi.org/project/patternforge/) do odkrywania wzorców |
| ArchWeave | [Produkt](https://www.archweave.dev/) do dokumentacji i wiedzy architektonicznej |
| Archloom | [Produkt w ofercie msoft](https://www.msoftstudio.pl/) dotyczący modeli architektury |
| ArchSynth | [Produkt AI](https://www.archsynth.com/) dla architektury i CAD |
| ArchSyn | [Wcześniejsza praca i narzędzie](https://hub.hku.hk/handle/10722/181525) do syntezy FPGA |

## Kolejność rozbudowy

1. Ustabilizować IR i testy semantyczne trzech wariantów. Raportować odrzucone warianty i założenia; nie traktować rankingów jako pomiarów.
2. Zweryfikować lokalne kontrakty reuse z uritime, autodo i forge. Oddzielić katalog znalezionych symboli od faktycznie działających adapterów.
3. Dodać pełne traceability user story → wymaganie → operacja → przepływ → reguła akceptacji.
4. Rozwinąć porównanie baseline/target i plan migracji z regułami importów oraz kompatybilności kontraktów.
5. Dodać walidowane eksporty CALM i Structurizr; ich testy powinny używać rzeczywistych parserów lub schematów przypiętych wersji.
6. Wprowadzić CP-SAT dopiero gdy liczba kandydatów i kombinacji uzasadnia solver. Raportować ograniczenia, cel, parametry i status dowodu.
7. Dodawać kolejne runtime lub frameworki agentowe wyłącznie dla brakujących funkcji, aby nie powielać uritime/autodo/subllm.

Najważniejszą przewagą ArchPat będzie spójne połączenie wymagań, ograniczeń, istniejącego kodu i planu migracji. Rysowanie diagramów oraz wywołanie LLM są pomocniczymi etapami tego procesu.
