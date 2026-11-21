from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
from .analysis import diff_graphs, impact
from .exporters import write_bundle
from .indexing import parse_toon, match_reuse, probe_workspace
from .io import json_text, read_json, write_json
from .ir_v2 import ArchitectureIRv2
from .models import ArchitectureGraph, StorySpec
from .operations import (
    coverage_operation,
    delta_operation,
    migrate_operation,
    validate_operation,
    view_operation,
)
from .synthesis import synthesize


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(prog="archpat", description="Pattern-aware architecture graph synthesis")
    command.add_argument("--version", action="version", version="archpat 0.1.0")
    subs = command.add_subparsers(dest="command", required=True)
    plan = subs.add_parser("synthesize", help="compare three CQRS+ES variants from a structured story")
    plan.add_argument("story")
    plan.add_argument("--index", action="append", default=[])
    plan.add_argument("--out", required=True)
    plan.add_argument("--overwrite", action="store_true")
    check = subs.add_parser("validate")
    check.add_argument("graph")
    index = subs.add_parser("index")
    index.add_argument("source")
    index.add_argument("--out")
    index.add_argument("--capability")
    probe = subs.add_parser("probe", help="read source metadata and AST without importing code")
    probe.add_argument("source", help="code2llm index")
    probe.add_argument("--root", required=True)
    probe.add_argument("--out")
    changes = subs.add_parser("diff")
    changes.add_argument("before")
    changes.add_argument("after")
    changes.add_argument("--out")
    affected = subs.add_parser("impact")
    affected.add_argument("graph")
    affected.add_argument("node")
    normal = subs.add_parser("normalize", help="LLM-only natural-language normalization, requires configured provider")
    normal.add_argument("text_file")
    normal.add_argument("--out", required=True)
    normal.add_argument("--base-url", default=os.getenv("ARCHPAT_LLM_BASE_URL", "http://localhost:11434/v1"))
    normal.add_argument("--model", default=os.getenv("ARCHPAT_LLM_MODEL"))
    normal.add_argument("--timeout", type=float, default=30)
    rest = subs.add_parser("serve")
    rest.add_argument("--host", default="127.0.0.1")
    rest.add_argument("--port", type=int, default=8765)
    subs.add_parser("mcp")
    schema = subs.add_parser("schema")
    schema.add_argument("kind", choices=["story", "graph", "ir-v2"])
    mig = subs.add_parser("migrate", help="migrate archpat.graph/v1 to archpat.ir/v2 with semantic hash")
    mig.add_argument("graph")
    mig.add_argument("--out")
    vw = subs.add_parser("view", help="extract one explicit architectural layer view from the IR")
    vw.add_argument("graph")
    vw.add_argument("--layer", choices=["domain", "data_flow", "deployment", "temporal", "implementation"], required=True)
    vw.add_argument("--out")
    cov = subs.add_parser("coverage", help="report user-story operation and acceptance-criteria coverage")
    cov.add_argument("graph")
    cov.add_argument("--out")
    dlt = subs.add_parser("delta", help="compare code2llm as-is indexes against a target architecture graph")
    dlt.add_argument("graph")
    dlt.add_argument("--index", action="append", required=True)
    dlt.add_argument("--out")
    return command


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        value = None
        if args.command == "synthesize":
            result = synthesize(StorySpec.model_validate(read_json(args.story)), [parse_toon(p) for p in args.index])
            paths = write_bundle(result, args.out, overwrite=args.overwrite)
            print(json_text({"status": result.status, "selected": result.selected_id,
                             "execution_ready": False, "files": paths}), end="")
            return 0 if result.selected_id else 2
        if args.command == "validate":
            value = validate_operation(read_json(args.graph))
            print(json_text(value), end="")
            return 0 if value["valid"] else 2
        if args.command == "index":
            value = parse_toon(args.source)
            if args.capability:
                value = {"project": value["project"], "candidates": match_reuse(value, args.capability)}
        elif args.command == "probe":
            value = probe_workspace(parse_toon(args.source), args.root)
        elif args.command == "diff":
            value = diff_graphs(ArchitectureGraph.model_validate(read_json(args.before)),
                                ArchitectureGraph.model_validate(read_json(args.after)))
        elif args.command == "impact":
            value = impact(ArchitectureGraph.model_validate(read_json(args.graph)), args.node)
        elif args.command == "normalize":
            from .llm import normalize_story
            if not args.model:
                raise ValueError("Set --model or ARCHPAT_LLM_MODEL; no model is downloaded automatically")
            raw = Path(args.text_file).read_text(encoding="utf-8")
            story, receipt = normalize_story(raw, base_url=args.base_url, model=args.model,
                                             api_key=os.getenv("ARCHPAT_LLM_API_KEY"), timeout=args.timeout)
            write_json(args.out, story.model_dump(mode="json"))
            write_json(str(args.out) + ".receipt.json", receipt)
            print(json_text({"story": args.out, "receipt": str(args.out) + ".receipt.json",
                             "semantic_review_required": True}), end="")
            return 0
        elif args.command == "serve":
            from .api import create_app
            import uvicorn
            uvicorn.run(create_app(), host=args.host, port=args.port)
            return 0
        elif args.command == "mcp":
            from .mcp_server import create_server
            create_server().run(transport="stdio")
            return 0
        elif args.command == "schema":
            model_cls = {"story": StorySpec, "graph": ArchitectureGraph, "ir-v2": ArchitectureIRv2}[args.kind]
            value = model_cls.model_json_schema()
        elif args.command == "migrate":
            value = migrate_operation(read_json(args.graph))
        elif args.command == "view":
            value = view_operation(read_json(args.graph), args.layer)
        elif args.command == "coverage":
            value = coverage_operation(read_json(args.graph))
        elif args.command == "delta":
            value = delta_operation(read_json(args.graph), [parse_toon(p) for p in args.index])
        if value is not None:
            if getattr(args, "out", None):
                write_json(args.out, value)
                print(json_text({"written": args.out}), end="")
            else:
                print(json_text(value), end="")
        return 0
    except (ValueError, OSError, RuntimeError, ImportError) as exc:
        print(json_text({"error": type(exc).__name__, "message": str(exc)}), file=sys.stderr, end="")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

