"""Portable graph artifacts. Diagramming is a view of the IR, not its authority."""
from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import networkx as nx
from .io import json_text
from .models import ArchitectureGraph, StorySpec, SynthesisResult
from .synthesis import fingerprint


def to_networkx(graph: ArchitectureGraph) -> nx.MultiDiGraph:
    result = nx.MultiDiGraph(id=graph.id, variant=graph.variant, schema_version=graph.schema_version)
    for node in graph.nodes:
        result.add_node(node.id, label=node.label, role=node.role, capability=node.capability,
                        process_group=node.process_group, owner=node.owner,
                        data=json.dumps(node.model_dump(mode="json"), ensure_ascii=False))
    for edge in graph.edges:
        result.add_edge(edge.source, edge.target, key=edge.id, kind=edge.kind,
                        effect=edge.effect, encoding=edge.encoding, interface=edge.interface,
                        data=json.dumps(edge.model_dump(mode="json"), ensure_ascii=False))
    return result


def mermaid(graph: ArchitectureGraph, *, view: str = "flow") -> str:
    if view not in {"flow", "dependencies"}:
        raise ValueError("view must be flow or dependencies")
    labels = {node.id: f"n{index}" for index, node in enumerate(graph.nodes)}

    def safe(text: str) -> str:
        # Mermaid entities avoid allowing labels to create directives or syntax.
        return (text.replace("&", "#38;").replace('"', "#34;").replace("<", "#60;")
                .replace(">", "#62;").replace("\n", " ").replace("\r", " "))
    lines = ["flowchart TD"]
    for node in graph.nodes:
        lines.append(f'  {labels[node.id]}["{safe(node.label)} · {node.role}"]')
    for edge in graph.edges:
        if edge.source not in labels or edge.target not in labels:
            continue
        if view == "dependencies" and edge.kind != "depends_on":
            continue
        if view == "flow" and edge.kind in {"depends_on", "return"}:
            continue
        lines.append(f'  {labels[edge.source]} -->|"{edge.kind}"| {labels[edge.target]}')
    return "\n".join(lines) + "\n"


def decision_markdown(result: SynthesisResult) -> str:
    lines = ["# Decyzja architektoniczna — ArchPat", "", f"Status: **{result.status}**.", "",
             f"Wybrany wariant: **{result.selected_id or 'brak dopuszczalnego wariantu'}**.", "",
             "Zakres: trzy jawne szablony CQRS + ES. Wynik nie stanowi dowodu optymalności poza katalogiem ani gotowości wykonania.", "",
             "| Wariant | Dopuszczalny | Nowe procesy | RAM aplikacji / razem [MiB, estymacja] | Koszt |",
             "|---|---:|---:|---:|---:|"]
    for item in result.candidates:
        m = item.metrics
        lines.append(f"| {item.id} | {'tak' if item.feasible else 'nie'} | {m.process_count} | {m.ram_mb_estimate} / {m.total_ram_mb_estimate} | {item.score if item.score is not None else '—'} |")
    lines += ["", "## Uzasadnienie i ograniczenia", ""]
    lines += [f"- {assumption}" for assumption in result.assumptions]
    for item in result.candidates:
        if item.rejection_reasons:
            lines += ["", f"### Odrzucenie: {item.id}", ""] + [f"- {reason}" for reason in item.rejection_reasons]
    if result.selected_id:
        selected = next(item for item in result.candidates if item.id == result.selected_id)
        lines += ["", "## Wymagania wymagające dalszej weryfikacji", ""]
        lines += [f"- {finding.code}: {finding.message}" for finding in selected.validation.findings]
        lines += ["", "## Kryteria akceptacji użytkownika", ""]
        lines += [f"- [ ] {criterion}" for criterion in selected.graph.story.acceptance_criteria]
        lines += ["", "Te kryteria są zachowane jako wymagania. ArchPat nie wykonał testów implementacji systemu docelowego.", ""]
    return "\n".join(lines) + "\n"


def handoff_proposal(graph: ArchitectureGraph) -> dict:
    return {"schema_version": "archpat.handoff-proposal/v1", "status": "unbound_proposal",
            "graph_sha256": fingerprint(graph.model_dump(mode="json")),
            "story_id": graph.story.id, "target_owners": {
                "time_semantics": "uritime_urt", "plan_and_schedule": "uritime",
                "goal_action_effects": "autodo", "implementation_qualification": "forge"},
            "runtime_process_uri": None, "canonical_urt_descriptor": None,
            "upstream_schema_verified": False, "submitted": False,
            "temporal_requirements": [op.temporal.model_dump(mode="json")
                                      for op in graph.story.operations if op.temporal],
            "required_local_read": ["planning/urt-polycell-forge-autonomy.md",
                                    "uritime/src/urievents/contracts.py",
                                    "packages/forge_base/forge_base/contracts.py"],
            "note": "ArchPat proposal format, not a claimed upstream command envelope."}


PROTO = '''syntax = "proto3";
package archpat.v1;
import "google/protobuf/struct.proto";

// Proposed ArchPat IR exchange. Not an upstream URT/urievents/domain API.
// Field numbers are stable in v1; reserve removed numbers and names.
message ArchitectureProposal {
  string schema_version = 1;
  string id = 2;
  string variant = 3;
  google.protobuf.Struct story = 4;
  repeated string patterns = 5;
  repeated Node nodes = 6;
  repeated Edge edges = 7;
  google.protobuf.Struct provenance = 8;
}
message ReuseEvidence {
  string project = 1;
  string path = 2;
  repeated string symbols = 3;
  optional string source_sha256 = 4;
  string status = 5;
  string note = 6;
}
message Node {
  string id = 1;
  string label = 2;
  string role = 3;
  string capability = 4;
  string owner = 5;
  string process_group = 6;
  repeated string story_ids = 7;
  optional string operation_id = 8;
  optional string aggregate_id = 9;
  string deployment = 10;
  optional string interface = 11;
  optional string service_url = 12;
  optional string process_uri = 13;
  string binding_status = 14;
  repeated ReuseEvidence reuse = 15;
  google.protobuf.Struct properties = 16;
}
message Edge {
  string id = 1;
  string source = 2;
  string target = 3;
  string kind = 4;
  optional string operation_id = 5;
  repeated string data_urns = 6;
  string effect = 7;
  string interface = 8;
  string encoding = 9;
  string delivery = 10;
  bool idempotent = 11;
  optional string transaction_group = 12;
}
'''


def write_bundle(result: SynthesisResult, output: str | Path, *, overwrite: bool = False) -> list[str]:
    target = Path(output)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and (not target.is_dir() or any(target.iterdir())) and not overwrite:
        raise FileExistsError(f"Output is not an empty directory: {target}. Use --overwrite for these generated artifacts.")
    with tempfile.TemporaryDirectory(prefix="archpat-", dir=target.parent) as temp:
        stage = Path(temp)
        (stage / "synthesis.json").write_text(json_text(result.model_dump(mode="json")), encoding="utf-8")
        (stage / "decision.md").write_text(decision_markdown(result), encoding="utf-8")
        (stage / "story.schema.json").write_text(json_text(StorySpec.model_json_schema()), encoding="utf-8")
        (stage / "graph.schema.json").write_text(json_text(ArchitectureGraph.model_json_schema()), encoding="utf-8")
        if result.selected_id:
            graph = next(c.graph for c in result.candidates if c.id == result.selected_id)
            (stage / "architecture.json").write_text(json_text(graph.model_dump(mode="json")), encoding="utf-8")
            (stage / "flow.mmd").write_text(mermaid(graph), encoding="utf-8")
            (stage / "dependencies.mmd").write_text(mermaid(graph, view="dependencies"), encoding="utf-8")
            nx.write_graphml(to_networkx(graph), stage / "architecture.graphml")
            (stage / "handoff-proposal.json").write_text(json_text(handoff_proposal(graph)), encoding="utf-8")
            if "protobuf" in graph.story.constraints.artifact_formats:
                (stage / "architecture.proto").write_text(PROTO, encoding="utf-8")
        paths = sorted(stage.iterdir())
        # Never silently leave a stale selected graph after an infeasible rerun.
        generated = {"architecture.json", "flow.mmd", "dependencies.mmd", "architecture.graphml",
                     "handoff-proposal.json", "architecture.proto"}
        target.mkdir(exist_ok=True)
        if overwrite:
            for name in generated - {path.name for path in paths}:
                stale = target / name
                if stale.is_file():
                    stale.unlink()
        for path in paths:
            os.replace(path, target / path.name)
        return [str(target / path.name) for path in paths]

