"""Bounded input and explicit artifact writes."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any

MAX_JSON_BYTES = 32 * 1024 * 1024


def loads_json(raw: str) -> Any:
    def pairs(items: list[tuple[str, Any]]) -> dict:
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    def bad_constant(value: str) -> None:
        raise ValueError(f"Non-finite JSON number is not allowed: {value}")
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=bad_constant)


def read_json(path: str | Path) -> Any:
    with Path(path).open("rb") as stream:
        raw = stream.read(MAX_JSON_BYTES + 1)
    if len(raw) > MAX_JSON_BYTES:
        raise ValueError("JSON file exceeds 32 MiB")
    return loads_json(raw.decode("utf-8"))


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"


def write_json(path: str | Path, value: Any, *, overwrite: bool = False) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w" if overwrite else "x", encoding="utf-8") as stream:
        stream.write(json_text(value))

