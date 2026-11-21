# Źródła, zależności i pochodzenie danych

Nowy kod ArchPat jest udostępniony w dołączonym pliku LICENSE. Biblioteki instalowane przez pip zachowują własne licencje. Nie są kopiowane do tego archiwum ani do wheel ArchPat.

Rdzeń używa Pydantic i NetworkX. Opcjonalne fasady korzystają z FastAPI, uvicorn oraz oficjalnego Python SDK MCP. Zależności i zakresy wersji są w `pyproject.toml`; wersje rzeczywiście testowane w `evidence/environment.json`.

`examples/indexes/uritime.toon.yaml` i `examples/indexes/forge.toon.yaml` są kopiami indeksów przekazanych przez użytkownika do tego zadania. Stanowią dane wejściowe demonstracji. Nie są checkoutami repozytoriów ani potwierdzeniem zgodności ich API. Ich skróty zapisano w `evidence/indexes.json`.

Dokumenty w `docs/` zawierają linki do źródeł pierwotnych OSS. Treści wskazanych repozytoriów Polycell i nl-uri-dsl-llm nie udało się odczytać przez dostępny odczyt web; nie wnioskujemy z tego o ich istnieniu, licencji lub prywatności.

Nazwa `archpat` jest robocza. Archiwum i wheel są przeznaczone do lokalnej instalacji; nie deklarują publikacji ani rezerwacji nazwy w PyPI.
