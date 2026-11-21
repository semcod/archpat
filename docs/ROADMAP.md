# Plan rozwoju Archpat

Poniższy backlog dotyczy dojścia od lokalnie weryfikowalnego prototypu do integracji z kodem użytkownika na PC. Jest planem nowych prac. Nie oznacza, że uruchomiono Forge, uritime, Polycell lub ich walidatory w obecnym środowisku.

Stan wobec dołączonego MVP 0.1.0: ARP-004 ma bazę w StorySpec/ArchitectureGraph; ARP-005 częściowo pokrywa walidacja referencji i handlerów; ARP-010 ma zaimplementowany zestaw reguł strukturalnych; ARP-011 ma ograniczony ranking trzech szablonów. Rozwijamy te moduły o brakujące dowody i integracje, zamiast implementować je ponownie. Import modeli rzeczywistego kodu, bindingi runtime, solver i kwalifikacja upstream pozostają pracami do wykonania.

Identyfikatory `ARP-*` są lokalnymi etykietami propozycji, nie utworzonymi ticketami. Indeks uritime wskazuje istniejący dokument `planning/urt-polycell-forge-autonomy.md` oraz katalog `planning/autonomy-pilot/`. Najpierw należy porównać ich rzeczywistą treść z tym backlogiem, powiązać pokrywające się zadania i dopisać wyłącznie brakujący zakres. Nie zakładać, że prace od zera są potrzebne dla każdej pozycji.

Każde zadanie kończy się artefaktem oraz określonym dowodem akceptacji. Status integracji powinien przechodzić przez `proposed` → `source_verified` → `contract_verified` → `integration_verified`. Wynik częściowy zachowuje najniższy niepotwierdzony poziom.

## Etap 1 — weryfikacja lokalnych źródeł

### ARP-001 — manifest dostępnych checkoutów i wersji

Zakres: wskazane przez użytkownika lokalne katalogi uritime, Forge, Polycell, nl-uri-dsl-llm, code2schema i Deconnected. Odczytać instrukcje projektów, manifesty paczek, publiczne eksporty, wersje oraz istniejący plan `planning/urt-polycell-forge-autonomy.md` i materiały `planning/autonomy-pilot/`. Zarejestrować URL repozytorium, commit lub hash drzewa, stan zmian lokalnych oraz ścieżki kontraktów. Nie dopisywać nieistniejących rewizji.

Wynik: `source-lock.json` z wartościami znanymi i jawnymi brakami. Akceptacja: każdy binding ma rozwiązywalne lokalne źródło albo status braku; ten etap nie zmienia checkoutów.

### ARP-002 — kontrakty uritime, URT i autodo

Zakres: odczytać rzeczywiste modele, publiczne metody i testy czasu, planowania, komend, zdarzeń oraz receipts. Ustalić właściciela każdego pola; opisać kolejność, timeout, deadline, anulowanie, ponowienie i idempotencję.

Wynik: macierz kontraktów z przykładami pobranymi z przypiętych źródeł. Akceptacja: potwierdzony przykład intencji czasu oraz przykład wyniku wykonania dają się odróżnić bez heurystyki nazw. Wcześniejszy, przyszły i dopiero rozważany stan mają różne znaczenie.

### ARP-003 — weryfikacja Polycell i standardu URI

Zakres: odczytać normatywne pliki wskazanych repozytoriów, porównać je z kopią schematu w Forge i sprawdzić faktycznie używaną rewizję. Zapisać ewentualne rozbieżności bez zastępowania lokalnych override'ów.

Wynik: raport adopcji i korpus przykładów. Akceptacja: przykłady poprawne i błędne przechodzą właściwy walidator upstream; żaden wymyślony kontrakt nie otrzymuje statusu potwierdzonego.

## Etap 2 — stabilny graf pośredni

### ARP-004 — wersjonowany IR i referencje

Zakres: utrwalić typy user story, ograniczenia, zdolności, kontekstu, portu, komendy, zapytania, zdarzenia, zasobu, projekcji, adaptera i relacji czasowej. Wprowadzić stabilne ID, wersje kontraktów i jawne pochodzenie. Oddzielić dane wejściowe, wniosek LLM, regułę i obserwację runtime.

Wynik: schemat IR oraz reguły migracji od wersji prototypu. Akceptacja: round-trip bez utraty pól normatywnych, odrzucenie zduplikowanych ID i wiszących referencji, deterministyczny hash semantycznej treści.

### ARP-005 — warstwy grafu i śledzenie realizacji user story

Zakres: rozdzielić logiczny model domeny, przepływ danych, wdrożenie, czas oraz istniejącą implementację jako widoki wspólnego IR. Dla każdego warunku akceptacji wskazać obsługujące węzły, ścieżkę i dowód lub brak dowodu.

Wynik: raport pokrycia user story i graf różnic `as-is` → `to-be`. Akceptacja: usunięcie węzła wymaganej ścieżki wywołuje konkretną diagnozę; niepełne dane nie zmieniają się w fałszywy dowód zgodności.

## Etap 3 — adaptery istniejących projektów

### ARP-006 — Forge: katalog, snapshot i reuse

Zakres: małe adaptery publicznych kontraktów `Catalog`, `SnapshotStore`, `ReuseIndex` oraz grafu z modułu `semcod`. Korzystać z wersjonowanych wejść/wyjść; nie wywoływać prywatnych pomocników przez ich nazwy z indeksu.

Wynik: biblioteka adapterów i jedna lokalna fixture snapshotu. Akceptacja: powtórna analiza tej samej tożsamości źródła daje ten sam zestaw dowodów; zmiana rewizji unieważnia odpowiednie dopasowania.

### ARP-007 — czas i plan: URT / uritime / autodo

Zakres: mapowanie deklaracji czasu z IR do potwierdzonego kontraktu URT, przygotowanie planu dla uritime i powiązanie wyniku autodo z węzłem i próbą wykonania. Zachować frazę NL, kotwicę, strefę czasową i wynik rozstrzygnięcia tam, gdzie upstream przewiduje takie dane.

Wynik: adapter planu i adapter receipt. Akceptacja: scenariusz „po ukończeniu A, przed terminem B” ma prawidłową kolejność; nierozstrzygnięty czas jest raportowany; replay faktów nie uruchamia skutków.

### ARP-008 — import as-is z code2schema / Deconnected

Zakres: import modeli istniejącego kodu i dowodów z granic modułów. Reuse istniejących ekstraktorów i generatorów po sprawdzeniu wersji. Oznaczyć heurystycznie wywnioskowane komendy i zapytania jako hipotezy.

Wynik: mapowanie do IR i raport różnic z grafem docelowym. Akceptacja: to samo źródło nie tworzy podwójnych bytów; brak runtime evidence nie jest interpretowany jako brak użycia; schematy zachowują wersje.

### ARP-009 — profile Polycell i nl-uri-dsl-llm

Zakres: wdrożyć mapowanie z ARP-003; konkretne URI walidować przez przypięty kontrakt; profil Polycell rozszerza IR przez jawne pole, nie wymusza niezweryfikowanej semantyki.

Wynik: dwa adaptery profilów i testy zgodności. Akceptacja: rzeczywiste przykłady upstream przechodzą import/eksport; nieobsługiwane semantyki powodują diagnozę i nie znikają z danych.

## Etap 4 — ograniczenia i porównywanie wariantów

### ARP-010 — reguły CQRS, ES i kontraktów

Zakres: reguły odpowiedzialności zapisu, odczytu projekcji, odbudowy, wersjonowania zdarzeń, idempotencji konsumenta i kolejności per aggregate. Dla rozdzielonego publikowania zdarzeń modelować atomowość zapisu i outbox. Weryfikować rozdział schematu danych od transportu.

Wynik: katalog fitness functions z identyfikatorami i uzasadnieniami. Akceptacja: przykłady query→mutation, podwójnego właściciela zapisu, nieistniejącego kontraktu i projekcji bez źródła zdarzeń dają diagnozy; poprawny mały model bez brokera pozostaje dopuszczalny, gdy spełnia ograniczenia.

### ARP-011 — optymalizacja wielokryterialna i kalibracja

Zakres: oddzielić twarde ograniczenia od wag preferencji, porównać tylko warianty dopuszczalne, raportować zbiór Pareto i wrażliwość wyboru na wagi. Pola dotyczące RAM, opóźnień i kosztu muszą wskazywać, czy pochodzą z pomiaru, estymacji czy założenia.

Wynik: odtwarzalny raport wyboru i profile zastosowań. Akceptacja: wariant łamiący twardy warunek nie wygrywa przez atrakcyjny score; zmiana wag może zmienić rekomendację z wyjaśnieniem. Wynik nie jest nazywany globalnym optimum bez dowodu i zdefiniowanej przestrzeni poszukiwań.

## Etap 5 — przekazanie do wykonania i kwalifikacja

### ARP-012 — plan migracji i zadań bez dublowania wykonawcy

Zakres: utworzyć plan `strangler` / `expand-contract`, kolejność adapterów kompatybilności, migrację projekcji i wycofanie starej ścieżki. Każde zadanie niesie zakres plików, preconditions, kontrakty oraz oczekiwane dowody. Powiązać zadania z istniejącymi ticketami, jeśli występują, zamiast bezwarunkowo je tworzyć.

Wynik: DAG prac i adapter przekazania do Forge lub istniejącego systemu planów. Akceptacja: plan nie zawiera cyklu, nie omija wymaganej zgodności wstecz i zachowuje tożsamości już istniejących zadań. Generowanie planu nie wywołuje jego wykonania.

### ARP-013 — kwalifikacja kandydata i dowody skutków

Zakres: użyć `project_jobs` i cyklu kandydata Forge po zweryfikowaniu kontraktów. Łączyć snapshot, patch, wersję architektury, środowisko, wyniki testów i receipts. Wyraźnie rozróżniać błąd infrastruktury od wadliwej implementacji.

Wynik: dossier kwalifikacji i reguły przyjęcia kandydata. Akceptacja: powtórzenie klucza idempotencji nie dubluje skutku; nieaktualny snapshot zatrzymuje kwalifikację; sam pozytywny test bez wymaganych dowodów nie zmienia statusu integracji na potwierdzony.

## Etap 6 — pilotaż i pomiar wartości

### ARP-014 — jeden pionowy scenariusz na PC

Zakres: pojedyncze user story o małym zakresie, np. przygotowanie oceny ćwiczenia po pojawieniu się wersjonowanego artefaktu. Porównać wariant modułowy, wariant z oddzielnym workerem i wariant rozproszony dla tych samych warunków. Użyć rzeczywistych lokalnych projektów i jednej ścieżki wykonania.

Wynik: pakiet user story → wymagania → warianty → decyzja → zadania → dowody. Akceptacja: uruchomienie z przypiętych źródeł, widoczny wynik i obsługa przerwania/ponowienia; ograniczenia i nieobsługiwane przypadki są opisane.

### ARP-015 — mierzenie kosztu zmian i gotowość wydania

Zakres: powtórzyć scenariusz ze zmianą kontraktu i z nowym adapterem, mierząc czas do wyniku, liczbę ręcznych poprawek, błędy kontraktów, zakres zmian oraz RAM/opóźnienie na PC. Oddzielić pomiary syntezy od czasu modeli i runtime. Zweryfikować nazwę dystrybucji, licencje i format wydania przed publikacją.

Wynik: raport porównawczy oraz decyzja o wersji nadającej się do codziennego użycia. Akceptacja: udokumentowana baza porównawcza, zidentyfikowane ograniczenia i brak twierdzenia o oszczędności procentowej bez pomiaru. Publikacja pakietu jest osobnym działaniem, którego ten backlog nie wykonuje.

## Minimalny warunek rozpoczęcia pilotażu

Pilotaż wymaga wykonanych ARP-001–007, odpowiednich profilów z ARP-009, reguł związanych z wybranym scenariuszem oraz jednej potwierdzonej ścieżki ARP-013. Pozostałe integracje mogą mieć jawny status nieaktywnego adaptera. Taki zakres pozwala sprawdzić wartość rozwiązania bez przebudowy całego ekosystemu.
