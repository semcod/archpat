# Weryfikacja wydania ArchPat 0.1.0

Data: 21 listopada 2026. Weryfikowano nową paczkę ArchPat w środowisku Python 3.12.14. Wersje najważniejszych bibliotek zapisano w `environment.json`.

## Wykonane kontrole

| Kontrola | Wynik | Dowód |
|---|---|---|
| Unit/integration suite | 77 testów, wszystkie zaliczone, bez pominięć | `unittest.txt` |
| Parser załączonego indeksu uritime | 647 pozycji, zgodne z M[] | `indexes.json` |
| Parser załączonego indeksu Forge | 574 pozycje, zgodne z M[] | `indexes.json` |
| Cztery zestawy ograniczeń | monolit / worker / usługi / brak dopuszczalnego wariantu | `example-run.json`, `../examples/generated/summary.json` |
| JSON Schema | StorySpec i grafy trzech wybranych wariantów przeszły walidację | `contracts.json` |
| Protobuf | kompilacja schematu i round-trip JSON → protobuf bytes → model dla trzech grafów | `contracts.json`, `../scripts/verify_contracts.py` |
| REST | żądania FastAPI TestClient, zgodność wyniku z granicą aplikacji, negatywna walidacja | testy w `unittest.txt` |
| MCP | rzeczywisty proces serwera stdio: initialize, list tools, synthesize, validate | `mcp.json`, `../scripts/verify_mcp.py` |
| LLM adapter | lokalny HTTP stub: format, naprawa schematu, limity i obsługa błędów | testy w `unittest.txt` |
| Dystrybucja wheel | zbudowano, zainstalowano do oddzielnego katalogu i uruchomiono syntezę z tej instalacji | `wheel.json`, `wheel-build.txt`, `wheel-install.txt` |

Kontrole obejmują ścieżki command/query/event, atomowość deklaracji outbox, właściciela agregatu, replay, checkpointy, idempotencję, niezależność grafu zależności od pętli biznesowych, stabilną walidację identyfikatorów, porównanie grafów, GraphML z równoległymi krawędziami oraz czyszczenie nieaktualnego wybranego grafu po wyniku niewykonalnym.

## Granice wyniku

- Nie uruchomiono Dockera: w środowisku nie ma klienta/daemona Docker. Dołączone Dockerfile i Compose są konfiguracją do sprawdzenia na PC.
- Nie uruchomiono `buf lint` ani `buf breaking`: Buf CLI nie jest dostępne. Kompilacja Protobuf została wykonana przez `grpcio-tools`; nie zastępuje to kontroli kompatybilności z poprzednim wydaniem.
- Nie wykonano żądania do rzeczywistego modelu LLM, Ollama ani LiteLLM. Test HTTP adaptera nie ocenia jakości interpretacji user stories.
- Nie uruchomiono uritime, URT, autodo, Forge, Polycell ani nl-uri-dsl-llm. Indeksy nie zawierają ich kodu i pełnych kontraktów. Nie ma potwierdzonej zgodności runtime.
- Nie zmierzono zużycia RAM ani opóźnień projektowanych systemów. Wartości w rankingu są jawnymi, umownymi priory. Ograniczenie pamięci jest więc sprawdzane warunkowo względem modelu kosztów.
- Testy nie realizują kryteriów biznesowych systemu edukacyjnego. Weryfikują generator i jego własne kontrakty.
- ArchPat nie publikuje paczki do PyPI, nie tworzy zdalnego repozytorium, nie zgłasza ticketów i nie wysyła planu do wykonania.

## Odtworzenie

```bash
make install
make test
make examples
make install-api
make install-mcp
.venv/bin/python -m pip install jsonschema grpcio-tools
.venv/bin/python scripts/verify_contracts.py
.venv/bin/python scripts/verify_mcp.py
make wheel
```

Testy REST są opcjonalne i zostaną pominięte, jeśli extras nie są zainstalowane. Aby odtworzyć pełny zestaw bez pominięć, po instalacji `[api,mcp]` uruchom ponownie `make test`. Plik `unittest.txt` pochodzi z pełnego środowiska z extras.

Wynik `execution_ready=false` pozostaje celowo niezmienny także przy pozytywnej walidacji struktury. Potwierdzenie działania konkretnego systemu należy do lokalnej kwalifikacji jego źródeł i adapterów.

