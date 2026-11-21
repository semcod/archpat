"""One application boundary used by shell, REST and MCP."""
from __future__ import annotations
from .analysis import diff_graphs, impact
from .ir_v2 import ArchitectureIRv2, migrate_v1_to_v2, semantic_hash, validate_ir_v2
from .models import ArchitectureGraph, StorySpec
from .synthesis import synthesize
from .validation import validate_graph
from .views_coverage import ViewLayer, as_is_to_be_delta, extract_view, story_coverage_report


def synthesize_operation(story: dict) -> dict:
    return synthesize(StorySpec.model_validate(story)).model_dump(mode="json")


def validate_operation(graph: dict) -> dict:
    if isinstance(graph, dict) and graph.get("schema_version") == "archpat.ir/v2":
        ir = ArchitectureIRv2.model_validate(graph)
        report = validate_ir_v2(ir)
        return {"valid": report.valid, "execution_ready": False, "semantic_hash": semantic_hash(ir),
                **report.model_dump(mode="json")}
    report = validate_graph(ArchitectureGraph.model_validate(graph))
    return {"valid": report.valid, "execution_ready": False, **report.model_dump(mode="json")}


def impact_operation(graph: dict, node_id: str) -> dict:
    return impact(ArchitectureGraph.model_validate(graph), node_id)


def diff_operation(before: dict, after: dict) -> dict:
    return diff_graphs(ArchitectureGraph.model_validate(before), ArchitectureGraph.model_validate(after))


def migrate_operation(graph: dict) -> dict:
    ir = migrate_v1_to_v2(ArchitectureGraph.model_validate(graph))
    return {"semantic_hash": semantic_hash(ir), "ir": ir.model_dump(mode="json")}


def view_operation(graph: dict, layer: ViewLayer) -> dict:
    parsed = (
        ArchitectureIRv2.model_validate(graph)
        if isinstance(graph, dict) and graph.get("schema_version") == "archpat.ir/v2"
        else ArchitectureGraph.model_validate(graph)
    )
    return extract_view(parsed, layer)


def coverage_operation(graph: dict) -> dict:
    parsed = (
        ArchitectureIRv2.model_validate(graph)
        if isinstance(graph, dict) and graph.get("schema_version") == "archpat.ir/v2"
        else ArchitectureGraph.model_validate(graph)
    )
    return story_coverage_report(parsed)


def delta_operation(target: dict, inventories: list[dict]) -> dict:
    parsed = (
        ArchitectureIRv2.model_validate(target)
        if isinstance(target, dict) and target.get("schema_version") == "archpat.ir/v2"
        else ArchitectureGraph.model_validate(target)
    )
    return as_is_to_be_delta(parsed, inventories)

