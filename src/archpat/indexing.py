"""Read code2llm text indexes and inspect local Python sources without imports.

An index is evidence of a reported symbol, not a verified implementation or API.
This module deliberately does not parse arbitrary YAML, run source code, discover
credentials, or import modules from an indexed workspace.
"""

from __future__ import annotations

import ast
import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import stat
import unicodedata
from typing import Any

MAX_INDEX_BYTES = 32 * 1024 * 1024
MAX_SOURCE_BYTES = 8 * 1024 * 1024


def _tokens(text: str) -> set[str]:
    plain = unicodedata.normalize("NFKD", text.casefold())
    plain = "".join(c for c in plain if not unicodedata.combining(c))
    return set(re.findall(r"[a-z0-9]+", plain))


def _add_symbol(module: dict[str, Any], value: str) -> None:
    symbol = value.strip()
    if symbol and symbol not in module["symbols"]:
        module["symbols"].append(symbol)


def parse_toon(path: Path | str) -> dict[str, Any]:
    """Parse the documented code2llm ``M[...]``/``D:`` text representation.

    Module order is retained. Symbols combine ``e:`` exports, function names,
    and qualified class methods. Unknown detail lines are ignored. ``loc`` is
    None for a detail-only module; reported counts are not silently reconciled.
    Invalid UTF-8, oversized input, or missing M/D sections raises ValueError.
    """
    source = Path(path)
    with source.open("rb") as handle:
        raw = handle.read(MAX_INDEX_BYTES + 1)
    if len(raw) > MAX_INDEX_BYTES:
        raise ValueError("code2llm index exceeds the size limit")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("code2llm index must be UTF-8 text") from exc

    modules: dict[str, dict[str, Any]] = {}
    project = source.stem
    header: dict[str, Any] = {}
    statistics: dict[str, Any] = {}
    section = ""
    saw_modules = False
    saw_details = False
    current: dict[str, Any] | None = None
    for line in text.splitlines():
        if line.startswith("#"):
            project_header = re.match(r"#\s*([^|]+)\|\s*(\d+)f\s+(\d+)L\s*\|", line)
            if project_header:
                project = project_header.group(1).strip()
                header["raw"] = line
                statistics["reported_file_count"] = int(project_header.group(2))
                statistics["reported_line_count"] = int(project_header.group(3))
                date = re.search(r"\|\s*(\d{4}-\d{2}-\d{2})\s*$", line)
                if date:
                    header["generated_at"] = date.group(1)
            if line.startswith("# producer:"):
                for key, value in re.findall(r"([a-z]+):\s*([^|]+)", line):
                    header[key] = value.strip()
            if line.startswith("# stats:"):
                for label, key in (("func", "reported_function_count"),
                                   ("cls", "reported_class_count"),
                                   ("mod", "reported_module_count")):
                    count = re.search(r"(\d+)\s+" + label + r"\b", line)
                    if count:
                        statistics[key] = int(count.group(1))
                cc = re.search(r"CC[^=|]*=([0-9]+(?:\.[0-9]+)?)", line)
                if cc:
                    statistics["reported_mean_cc"] = float(cc.group(1))
                critical = re.search(r"critical:(\d+)", line)
                if critical:
                    statistics["reported_critical_count"] = int(critical.group(1))
                cycles = re.search(r"cycles:([^|\s]+)", line)
                if cycles:
                    statistics["reported_cycles"] = cycles.group(1)
            continue
        module_header = re.fullmatch(r"M\[(\d+)\]:\s*", line)
        if module_header:
            section, saw_modules = "M", True
            statistics["declared_module_count"] = int(module_header.group(1))
            continue
        if line.strip() == "D:" and not line.startswith(" "):
            section, saw_details = "D", True
            continue
        if section == "M":
            entry = re.fullmatch(r"  (.+),(\d+)\s*", line)
            if entry:
                name, loc = entry.groups()
                if name in modules:
                    raise ValueError(f"duplicate module in M section: {name}")
                modules[name] = {"path": name, "loc": int(loc), "symbols": []}
        elif section == "D":
            module_detail = re.fullmatch(r"  (\S.*):\s*", line)
            if module_detail:
                name = module_detail.group(1)
                current = modules.setdefault(name, {"path": name, "loc": None, "symbols": []})
                continue
            if current is None:
                continue
            if line.startswith("    e: "):
                for symbol in line[7:].split(","):
                    _add_symbol(current, symbol)
                continue
            class_detail = re.match(r"    ([A-Za-z_]\w*)(?:\([^)]*\))?:\s*(.*)", line)
            if class_detail:
                class_name, methods = class_detail.groups()
                if class_name in {"i", "e", "c", "f", "m"}:
                    continue
                _add_symbol(current, class_name)
                for method in re.findall(r"([A-Za-z_]\w*)\(-?\d+\)", methods.split("#", 1)[0]):
                    _add_symbol(current, f"{class_name}.{method}")
                continue
            function = re.match(r"    ([A-Za-z_]\w*)\(", line)
            if function:
                _add_symbol(current, function.group(1))

    if not saw_modules or not saw_details:
        raise ValueError("expected code2llm M[count]: and D: sections; this is not a generic YAML parser")
    statistics["parsed_module_count"] = len(modules)
    statistics["parsed_symbol_count"] = sum(len(module["symbols"]) for module in modules.values())
    return {
        "project": project,
        "source": str(source),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "header": header,
        "stats": statistics,
        "evidence": "indexed_only",
        "api_verified": False,
        "modules": list(modules.values()),
    }


_TERMS = {
    "urt": {"temporal", "resolution", "recurrence", "occurrences", "urt"},
    "time": {"temporal", "resolution", "scheduler", "schedule", "recurrence"},
    "czas": {"temporal", "resolution", "scheduler", "schedule", "recurrence"},
    "temporal": {"temporal", "resolution", "selectors", "monitor", "recurrence"},
    "schedule": {"schedule", "scheduler", "planledger", "handoff", "materializer"},
    "plan": {"planledger", "propose", "plan", "scheduler", "planfile"},
    "cqrs": {"cqrs", "commands", "queries", "commandenvelope", "domaineventenvelope"},
    "es": {"events", "event", "projections", "outbox", "replay"},
    "event": {"events", "event", "projections", "outbox", "replay", "importers"},
    "data": {"data", "dataref", "datarecord", "pinning", "urn", "vault"},
    "urn": {"dataref", "datarecord", "pinning", "urn", "dataregistryport"},
    "url": {"servicebinding", "connector", "binding", "connectorexecutor"},
    "uri": {"processref", "operationuri", "operation", "descriptor", "registry"},
    "llm": {"subllm", "llm", "modelport", "synthesizer", "gateway"},
    "rest": {"rest", "api", "server", "facade"},
    "mcp": {"mcp", "urtmcpserver", "server"},
    "shell": {"cli", "shell", "argv", "parser"},
    "protobuf": {"protobuf", "proto"},
    "forge": {"forge", "manager", "snapshots", "qualification", "catalog"},
    "polycell": {"polycell", "cell", "cells"},
    "ownership": {"ownership", "fence", "generation", "authoritativedispatchgate"},
}


def match_reuse(inventory: dict[str, Any], capability: str) -> list[dict[str, Any]]:
    """Rank up to twenty lexical candidates, never assert semantic/API fitness.

    ``score`` is an explainable token score (path=2, symbol=4), not a measured
    compatibility probability. Explicit aliases help explore the known domain.
    """
    requested = _tokens(capability)
    if not requested:
        return []
    terms = set(requested)
    for token in requested:
        terms.update(_TERMS.get(token, ()))
    matches = []
    for module in inventory.get("modules", []):
        path_terms = _tokens(module["path"])
        symbol_terms = _tokens(" ".join(module.get("symbols", [])))
        path_hits = terms & path_terms
        symbol_hits = terms & symbol_terms
        score = 2 * len(path_hits) + 4 * len(symbol_hits)
        if score:
            matches.append({
                "project": inventory.get("project"),
                "path": module["path"],
                "loc": module.get("loc"),
                "symbols": list(module.get("symbols", [])),
                "score": score,
                "matched_terms": sorted(path_hits | symbol_hits),
                "evidence": "indexed_only",
                "api_verified": False,
                "source_sha256": inventory.get("sha256"),
            })
    return sorted(matches, key=lambda item: (-item["score"], item["path"]))[:20]


class _Definitions(ast.NodeVisitor):
    def __init__(self) -> None:
        self.prefix: list[str] = []
        self.symbols: list[str] = []

    def _definition(self, node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self.prefix.append(node.name)
        self.symbols.append(".".join(self.prefix))
        self.generic_visit(node)
        self.prefix.pop()

    visit_ClassDef = _definition
    visit_FunctionDef = _definition
    visit_AsyncFunctionDef = _definition


def _source_path(root: Path, value: str) -> Path:
    relative = PurePosixPath(value)
    if not value or relative.is_absolute() or ".." in relative.parts or "\\" in value:
        raise ValueError("indexed path must be a relative contained POSIX path")
    if any(ord(c) < 32 for c in value):
        raise ValueError("control character in indexed path")
    candidate = root.joinpath(*relative.parts)
    # Reject symlinks, including internal ones, to keep provenance unambiguous.
    component = root
    for part in relative.parts:
        component /= part
        if component.is_symlink():
            raise ValueError("symlinks are not followed during a source probe")
    candidate.resolve().relative_to(root)
    return candidate


def probe_workspace(inventory: dict[str, Any], root: Path | str) -> dict[str, Any]:
    """Inspect contained source files with stat, hashing and AST only.

    Python files are bounded to MAX_SOURCE_BYTES. Other indexed files are only
    stat'ed. Missing AST definitions may be re-exports or stale index entries;
    they never prove a broken runtime API. No imports or code execution occur.
    """
    base = Path(root).resolve(strict=True)
    if not base.is_dir():
        raise ValueError("workspace root must be a directory")
    observations = []
    for module in inventory.get("modules", []):
        observation: dict[str, Any] = {
            "path": module["path"],
            "evidence": "filesystem_only",
            "api_verified": False,
        }
        try:
            path = _source_path(base, module["path"])
        except (ValueError, OSError) as exc:
            observation.update(status="unsafe_path", reason=str(exc))
            observations.append(observation)
            continue
        try:
            metadata = path.stat()
            if not stat.S_ISREG(metadata.st_mode):
                observation["status"] = "not_regular_file"
            elif path.suffix != ".py":
                observation.update(status="present_non_python", size_bytes=metadata.st_size)
            elif metadata.st_size > MAX_SOURCE_BYTES:
                observation.update(status="source_too_large", size_bytes=metadata.st_size)
            else:
                flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
                descriptor = os.open(path, flags)
                with os.fdopen(descriptor, "rb") as handle:
                    if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                        raise ValueError("source changed to a non-regular file")
                    raw = handle.read(MAX_SOURCE_BYTES + 1)
                if len(raw) > MAX_SOURCE_BYTES:
                    observation.update(status="source_too_large", size_bytes=len(raw))
                else:
                    observation.update(size_bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
                    try:
                        tree = ast.parse(raw, filename=module["path"])
                    except (SyntaxError, ValueError, UnicodeError) as exc:
                        observation.update(status="parse_error", reason=str(exc))
                    else:
                        definitions = _Definitions()
                        definitions.visit(tree)
                        observation.update(
                            status="source_observed",
                            evidence="source_ast_only",
                            symbols=definitions.symbols,
                            unobserved_index_symbols=sorted(
                                set(module.get("symbols", [])) - set(definitions.symbols)
                            ),
                        )
        except FileNotFoundError:
            observation["status"] = "missing"
        except (OSError, ValueError) as exc:
            observation.update(status="unreadable", reason=str(exc))
        observations.append(observation)
    counts: dict[str, int] = {}
    for observation in observations:
        status = observation["status"]
        counts[status] = counts.get(status, 0) + 1
    return {
        "project": inventory.get("project"),
        "root": str(base),
        "inventory_sha256": inventory.get("sha256"),
        "mode": "stat_sha256_ast_only",
        "api_verified": False,
        "summary": counts,
        "modules": observations,
    }
