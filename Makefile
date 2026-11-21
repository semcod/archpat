PYTHON ?= python3
VENV ?= .venv
BIN := $(VENV)/bin
OUT ?= build/demo

.PHONY: install install-api install-mcp test pilot demo examples serve mcp wheel docker-test docker-demo
install:
	$(PYTHON) -m venv $(VENV)
	$(BIN)/python -m pip install -e .

install-api: install
	$(BIN)/python -m pip install -e '.[api]'

install-mcp: install
	$(BIN)/python -m pip install -e '.[mcp]'

test:
	$(BIN)/python -m unittest discover -s tests -v

pilot:
	$(BIN)/python scripts/run_pilot.py

demo:
	$(BIN)/archpat synthesize examples/story-local.json --index examples/indexes/uritime.toon.yaml --index examples/indexes/forge.toon.yaml --out $(OUT) --overwrite

examples:
	$(BIN)/python scripts/run_examples.py

serve:
	$(BIN)/archpat serve

mcp:
	$(BIN)/archpat mcp

wheel:
	$(BIN)/python -m pip wheel --no-deps --no-build-isolation . -w dist

docker-test:
	docker compose run --rm tests

docker-demo:
	mkdir -p build/docker
	LOCAL_UID=$$(id -u) LOCAL_GID=$$(id -g) docker compose run --rm demo

