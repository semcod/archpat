#!/usr/bin/env python3
"""ARP-001: Generate evidence/source-lock.json from local PC checkouts (read-only)."""

from __future__ import annotations

import hashlib
import json
import subprocess
import tomllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "evidence" / "source-lock.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_info(path: Path) -> dict[str, Any]:
    if not (path / ".git").exists():
        return {"is_git_repo": False}

    def run(*args: str) -> str:
        proc = subprocess.run(
            ["git", "-C", str(path), *args],
            capture_output=True,
            text=True,
            check=False,
        )
        return proc.stdout.strip() if proc.returncode == 0 else ""

    status = run("status", "--porcelain")
    dirty_lines = [line for line in status.splitlines() if line.strip()]
    return {
        "is_git_repo": True,
        "remote_origin": run("remote", "get-url", "origin") or None,
        "branch": run("rev-parse", "--abbrev-ref", "HEAD") or None,
        "head_commit": run("rev-parse", "HEAD") or None,
        "head_date": run("show", "-s", "--format=%cI", "HEAD") or None,
        "dirty_count": len(dirty_lines),
        "clean": len(dirty_lines) == 0,
    }


def _pyproject_info(path: Path) -> dict[str, Any] | None:
    pyproject = path / "pyproject.toml"
    if not pyproject.is_file():
        return None
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    project = data.get("project", {})
    lic = project.get("license")
    if isinstance(lic, dict):
        lic = lic.get("text") or lic.get("file")
    return {
        "name": project.get("name"),
        "version": project.get("version"),
        "license": lic,
        "pyproject_sha256": _sha256(pyproject),
    }


def _contract_entries(base: Path, rel_paths: list[str]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for rel in rel_paths:
        target = base / rel
        if target.is_file():
            entries.append(
                {
                    "path": rel,
                    "exists": True,
                    "size_bytes": target.stat().st_size,
                    "sha256": _sha256(target),
                }
            )
        else:
            entries.append({"path": rel, "exists": False})
    return entries


def build_source_lock(github_root: Path = Path("/home/tom/github")) -> dict[str, Any]:
    specs: list[dict[str, Any]] = [
        {
            "id": "uritime-workspace",
            "path": github_root / "uritime",
            "role": "Umbrella workspace holding uritime, urt, autodo, autonom, urtlog, wheelhouse, and autonomy-pilot",
            "contracts": [
                "planning/urt-polycell-forge-autonomy.md",
                "planning/autonomy-pilot/README.md",
                "planning/autonomy-pilot/contracts/cells/backlog.reconciliation.cell.yaml",
                "planning/autonomy-pilot/cells/python/backlog_reconciliation.py",
            ],
        },
        {
            "id": "uritime",
            "path": github_root / "uritime" / "uritime",
            "role": "Plan/Schedule single-writer ledger, UriEventStore, ur-cqrs-v1 and urt-record-v1 contracts",
            "contracts": [
                "src/urievents/contracts.py",
                "src/urievents/store.py",
                "src/urievents/schemas/ur-cqrs-v1.schema.json",
                "src/urievents/schemas/urt-record-v1.schema.json",
                "src/urievents/schemas/urt-record-data-v1.schema.json",
                "src/uritime/plan_commands.py",
                "src/uritime/plan_queries.py",
            ],
        },
        {
            "id": "uritime-urt",
            "path": github_root / "uritime" / "urt",
            "role": "URT v1 canonical temporal descriptors, AST validation, and deterministic intent resolution",
            "contracts": [
                "src/uritime_urt/intents.py",
                "src/uritime_urt/resolution.py",
                "src/uritime_urt/schemas/descriptor-v1.schema.json",
                "src/uritime_urt/schemas/temporal-intent-v1.schema.json",
                "src/uritime_urt/schemas/temporal-monitor-v1.schema.json",
                "src/uritime_urt/schemas/resolution-v1.schema.json",
            ],
        },
        {
            "id": "uritime-autodo",
            "path": github_root / "uritime" / "autodo",
            "role": "Goal/Action execution, operation descriptors, service bindings, and data pinning",
            "contracts": [
                "src/subactor_autonomy/operation_descriptor.py",
                "src/subactor_autonomy/service_binding.py",
                "src/subactor_autonomy/data_pinning.py",
                "src/subactor_autonomy/ownership.py",
            ],
        },
        {
            "id": "uritime-autonom",
            "path": github_root / "uritime" / "autonom",
            "role": "Candidate decision synthesis and SubLLM client",
            "contracts": ["src/autonom/synthesizer.py"],
        },
        {
            "id": "uritime-urtlog",
            "path": github_root / "uritime" / "urtlog",
            "role": "Unified URL/URI/URN/URT log and registry facade",
            "contracts": ["src/urtlog/dsl.py", "src/urtlog/registry.py"],
        },
        {
            "id": "forge",
            "path": github_root / "paxlet-com" / "forge",
            "role": "Immutable Git-commit snapshots, project_jobs patch qualification, process contracts, and Wellman pins",
            "contracts": [
                "packages/forge_base/forge_base/snapshots.py",
                "packages/forge_base/forge_base/project_jobs.py",
                "packages/forge_base/forge_base/contracts.py",
                "packages/forge_base/forge_base/catalog.py",
                "packages/forge_wellman/forge_wellman/upstream-pins.json",
                "examples/wellman/standards/nl-uri-dsl-llm/process-uri.schema.json",
                "examples/wellman/standards/data-plane/process-exchange.schema.json",
            ],
        },
        {
            "id": "heyasa",
            "path": github_root / "paxlet-com" / "heyasa",
            "role": "Host ecosystem orchestrator consuming uritime temporal runtime and urtlog",
            "contracts": [
                "heyasa/temporal_runtime.py",
                "heyasa/urt_cqrs_adapter.py",
                "docs/decisions/heyasa-uritime-autonom-boundary-2026-11-18.md",
            ],
        },
        {
            "id": "wellmanifest-polycell",
            "path": github_root / "wellmanifest" / "polycell",
            "role": "Contract-first replaceable cell architecture (Python/TS/Rust) and POA process plans",
            "contracts": [
                "standard/polycell-cell.schema.v1.json",
                "standard/polycell-plan.schema.v1.json",
                "standard/polycell-package.schema.v1.json",
                "standard/conformance.py",
                "contracts/cells/pricing.quote.cell.yaml",
                "contracts/processes/checkout.process.yaml",
            ],
        },
        {
            "id": "wellmanifest-nl-uri-dsl-llm",
            "path": github_root / "wellmanifest" / "nl-uri-dsl-llm",
            "role": "Normative NL -> RFC 3986 Action URI / Resource URN -> LLM GBNF standard",
            "contracts": [
                "schemas/process-uri.schema.json",
                "schemas/mcp-process-gateway.schema.json",
                "schemas/system-one-decision.schema.json",
                "profiles/semantic-v1.json",
            ],
        },
        {
            "id": "wellmanifest-nl-dsl-llm",
            "path": github_root / "wellmanifest" / "nl-dsl-llm",
            "role": "Companion NL -> DSL -> LLM standard",
            "contracts": ["README.md"],
        },
        {
            "id": "code2schema",
            "path": github_root / "autogrammar" / "code2schema",
            "role": "Static AST -> CQRS heuristic extractor (as-is hypothesis source)",
            "contracts": ["code2schema/__init__.py", "LICENSE"],
        },
        {
            "id": "deconnected",
            "path": github_root / "autogrammar" / "deconnected",
            "role": "Extraction boundary / dependency graph analyzer (optional external tool)",
            "contracts": [],
        },
    ]

    sources: list[dict[str, Any]] = []
    for spec in specs:
        raw_path = Path(spec["path"])
        if not raw_path.exists():
            sources.append(
                {
                    "id": spec["id"],
                    "status": "missing_local_checkout",
                    "requested_path": str(raw_path),
                    "role": spec["role"],
                    "contracts": [],
                }
            )
            continue
        real_path = raw_path.resolve()
        sources.append(
            {
                "id": spec["id"],
                "status": "source_verified",
                "requested_path": str(raw_path),
                "resolved_path": str(real_path),
                "role": spec["role"],
                "git": _git_info(real_path),
                "package": _pyproject_info(real_path),
                "contracts": _contract_entries(real_path, spec["contracts"]),
            }
        )

    # Explicit cross-repo checksum check: nl-uri-dsl-llm process-uri.schema.json vs Forge copy
    nl_schema = github_root / "wellmanifest" / "nl-uri-dsl-llm" / "schemas" / "process-uri.schema.json"
    forge_schema = (
        github_root / "paxlet-com" / "forge" / "examples" / "wellman" / "standards"
        / "nl-uri-dsl-llm" / "process-uri.schema.json"
    )
    cross_checks: dict[str, Any] = {}
    if nl_schema.is_file() and forge_schema.is_file():
        nl_hash = _sha256(nl_schema)
        forge_hash = _sha256(forge_schema)
        cross_checks["nl_uri_process_schema_vs_forge_copy"] = {
            "upstream_path": str(nl_schema.resolve()),
            "forge_copy_path": str(forge_schema.resolve()),
            "upstream_sha256": nl_hash,
            "forge_copy_sha256": forge_hash,
            "identical": nl_hash == forge_hash,
        }

    return {
        "schema": "archpat.source-lock/v1",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "archpat_root": str(ROOT),
        "evidence_level": "source_verified",
        "note": "Read-only inventory of local PC checkouts; no sibling checkouts were modified.",
        "sources": sources,
        "cross_checks": cross_checks,
    }


def main() -> int:
    lock = build_source_lock()
    DEFAULT_OUT.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_OUT.write_text(json.dumps(lock, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    present = sum(1 for s in lock["sources"] if s["status"] == "source_verified")
    missing = [s["id"] for s in lock["sources"] if s["status"] != "source_verified"]
    print(json.dumps({"written": str(DEFAULT_OUT), "present": present, "missing": missing}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
