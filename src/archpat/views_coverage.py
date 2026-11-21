"""ARP-005: Multi-layer graph views, user-story acceptance coverage, and as-is -> to-be delta."""

from __future__ import annotations

from typing import Any, Literal

import networkx as nx

from .indexing import match_reuse
from .ir_v2 import ArchitectureIRv2, migrate_v1_to_v2, semantic_hash
from .models import ArchitectureGraph
from .validation import validate_graph

ViewLayer = Literal["domain", "data_flow", "deployment", "temporal", "implementation"]

_DOMAIN_ROLES = frozenset(
    {"actor", "command_handler", "query_handler", "aggregate", "event_store", "outbox", "relay", "projector", "read_model"}
)
_DOMAIN_EDGE_KINDS = frozenset({"command", "query", "event", "read", "write", "invoke", "return"})


def _as_v2(graph: ArchitectureGraph | ArchitectureIRv2) -> ArchitectureIRv2:
    if isinstance(graph, ArchitectureIRv2):
        return graph
    return migrate_v1_to_v2(graph)


def extract_view(graph: ArchitectureGraph | ArchitectureIRv2, layer: ViewLayer) -> dict[str, Any]:
    """Project one explicit view over the shared IR without mutating or losing underlying nodes."""
    ir = _as_v2(graph)
    nodes_by_id = {item.node.id: item for item in ir.nodes}

    if layer == "domain":
        sel_nodes = [item.node.id for item in ir.nodes if item.node.role in _DOMAIN_ROLES]
        sel_set = set(sel_nodes)
        sel_edges = [
            item.edge.model_dump(mode="json")
            for item in ir.edges
            if item.edge.kind in _DOMAIN_EDGE_KINDS and item.edge.source in sel_set and item.edge.target in sel_set
        ]
        return {
            "schema_version": "archpat.view/v1",
            "layer": layer,
            "graph_id": ir.id,
            "semantic_hash": semantic_hash(ir),
            "nodes": [nodes_by_id[nid].node.model_dump(mode="json") for nid in sel_nodes],
            "edges": sel_edges,
        }

    if layer == "data_flow":
        sel_edges = [
            item.edge
            for item in ir.edges
            if item.edge.data_urns or item.edge.kind in {"read", "write", "event", "command", "return"}
        ]
        involved = sorted({e.source for e in sel_edges} | {e.target for e in sel_edges})
        return {
            "schema_version": "archpat.view/v1",
            "layer": layer,
            "graph_id": ir.id,
            "semantic_hash": semantic_hash(ir),
            "data_urns": sorted({urn for e in sel_edges for urn in e.data_urns}),
            "nodes": [nodes_by_id[nid].node.model_dump(mode="json") for nid in involved if nid in nodes_by_id],
            "edges": [e.model_dump(mode="json") for e in sel_edges],
        }

    if layer == "deployment":
        groups: dict[str, list[dict[str, Any]]] = {}
        for item in ir.nodes:
            groups.setdefault(item.node.process_group, []).append(
                {
                    "id": item.node.id,
                    "role": item.node.role,
                    "deployment": item.node.deployment,
                    "owner": item.node.owner,
                }
            )
        cross_edges = [
            item.edge.model_dump(mode="json")
            for item in ir.edges
            if item.edge.kind != "depends_on"
            and item.edge.source in nodes_by_id
            and item.edge.target in nodes_by_id
            and nodes_by_id[item.edge.source].node.process_group
            != nodes_by_id[item.edge.target].node.process_group
        ]
        return {
            "schema_version": "archpat.view/v1",
            "layer": layer,
            "graph_id": ir.id,
            "variant": ir.variant,
            "semantic_hash": semantic_hash(ir),
            "process_groups": {k: groups[k] for k in sorted(groups)},
            "cross_process_edges": cross_edges,
        }

    if layer == "temporal":
        temporal_ops = [op for op in ir.story.operations if op.temporal is not None]
        temporal_op_ids = {op.id for op in temporal_ops}
        sel_edges = [
            item.edge
            for item in ir.edges
            if item.edge.kind in {"temporal", "propose"} or item.edge.operation_id in temporal_op_ids
        ]
        sel_node_ids = sorted(
            {item.node.id for item in ir.nodes if item.node.role == "temporal_service" or item.node.operation_id in temporal_op_ids}
            | {e.source for e in sel_edges}
            | {e.target for e in sel_edges}
        )
        return {
            "schema_version": "archpat.view/v1",
            "layer": layer,
            "graph_id": ir.id,
            "semantic_hash": semantic_hash(ir),
            "temporal_requirements": [
                {"operation_id": op.id, **op.temporal.model_dump(mode="json")}
                for op in temporal_ops
                if op.temporal is not None
            ],
            "nodes": [nodes_by_id[nid].node.model_dump(mode="json") for nid in sel_node_ids if nid in nodes_by_id],
            "edges": [e.model_dump(mode="json") for e in sel_edges],
        }

    if layer == "implementation":
        bindings = []
        for item in ir.nodes:
            bindings.append(
                {
                    "node_id": item.node.id,
                    "role": item.node.role,
                    "owner": item.node.owner,
                    "binding_status": item.node.binding_status,
                    "evidence_level": item.evidence_level,
                    "reuse_candidates": [r.model_dump(mode="json") for r in item.node.reuse],
                    "profiles": item.profiles.model_dump(mode="json"),
                }
            )
        return {
            "schema_version": "archpat.view/v1",
            "layer": layer,
            "graph_id": ir.id,
            "semantic_hash": semantic_hash(ir),
            "execution_ready": False,
            "bindings": bindings,
        }

    raise ValueError(f"Unsupported view layer: {layer!r}")


def story_coverage_report(graph: ArchitectureGraph | ArchitectureIRv2) -> dict[str, Any]:
    """ARP-005: Trace every operation and acceptance criterion to graph paths, diagnosing missing nodes/edges."""
    ir = _as_v2(graph)
    v1 = ir.to_v1_graph()
    validation = validate_graph(v1)
    nodes = {item.node.id: item for item in ir.nodes}

    flow = nx.DiGraph()
    flow.add_nodes_from(nodes)
    for item in ir.edges:
        if item.edge.kind != "depends_on" and item.edge.source in nodes and item.edge.target in nodes:
            flow.add_edge(item.edge.source, item.edge.target, kind=item.edge.kind, operation_id=item.edge.operation_id)

    # Check structural completeness per operation
    operation_reports: list[dict[str, Any]] = []
    op_diagnostics: dict[str, list[str]] = {}

    for op in ir.story.operations:
        diags: list[str] = []
        expected_role = "command_handler" if op.kind == "command" else "query_handler"
        handlers = [n for n in ir.nodes if n.node.operation_id == op.id and n.node.role == expected_role]
        path_nodes: list[str] = []

        if len(handlers) != 1:
            diags.append(f"missing_or_duplicate_{expected_role}: expected 1 handler for operation '{op.id}', found {len(handlers)}")
        else:
            handler_id = handlers[0].node.id
            path_nodes.append(handler_id)
            for iface in ir.story.constraints.interfaces:
                adapters = [n.node.id for n in ir.nodes if n.node.role == "adapter" and n.node.interface == iface]
                if not any(flow.has_edge(a, handler_id) for a in adapters):
                    diags.append(f"missing_interface_path:{iface}->{handler_id}")
                else:
                    path_nodes.extend(a for a in adapters if flow.has_edge(a, handler_id))

            if op.kind == "command":
                agg_id = f"aggregate.{op.aggregate}"
                if agg_id not in nodes or not flow.has_edge(handler_id, agg_id):
                    diags.append(f"broken_command_aggregate_path:{handler_id}->{agg_id}")
                else:
                    path_nodes.append(agg_id)
                    event_stores = [n.node.id for n in ir.nodes if n.node.role == "event_store"]
                    if not any(flow.has_edge(agg_id, es) for es in event_stores):
                        diags.append(f"missing_event_store_write:{agg_id}->event_store")
                    else:
                        path_nodes.extend(es for es in event_stores if flow.has_edge(agg_id, es))
                    outboxes = [n.node.id for n in ir.nodes if n.node.role == "outbox"]
                    projectors = [n.node.id for n in ir.nodes if n.node.role == "projector"]
                    read_models = [n.node.id for n in ir.nodes if n.node.role == "read_model"]
                    if "outbox" in ir.patterns:
                        if not any(flow.has_edge(agg_id, ob) for ob in outboxes):
                            diags.append(f"missing_outbox_write:{agg_id}->outbox")
                        if not any(nx.has_path(flow, ob, pr) for ob in outboxes for pr in projectors):
                            diags.append("broken_outbox_to_projector_delivery")
                        else:
                            path_nodes.extend(outboxes + projectors)
                    if not any(flow.has_edge(pr, rm) for pr in projectors for rm in read_models):
                        diags.append("broken_projector_to_read_model_path")
                    else:
                        path_nodes.extend(read_models)
            else:
                read_models = [n.node.id for n in ir.nodes if n.node.role == "read_model"]
                if not any(flow.has_edge(handler_id, rm) for rm in read_models):
                    diags.append(f"broken_query_read_model_path:{handler_id}->read_model")
                else:
                    path_nodes.extend(rm for rm in read_models if flow.has_edge(handler_id, rm))

            if op.temporal is not None:
                temporal_nodes = [n.node.id for n in ir.nodes if n.node.role == "temporal_service"]
                if not temporal_nodes or not any(flow.has_edge(t, handler_id) for t in temporal_nodes):
                    diags.append(f"missing_temporal_service_path:uritime->{handler_id}")
                else:
                    path_nodes.extend(t for t in temporal_nodes if flow.has_edge(t, handler_id))

        op_diagnostics[op.id] = diags
        evidence_levels = [nodes[nid].evidence_level for nid in path_nodes if nid in nodes]
        all_runtime_verified = bool(evidence_levels) and all(
            lvl in {"contract_verified", "integration_verified"} for lvl in evidence_levels
        )
        status = (
            "gap_detected"
            if diags
            else ("evidence_verified" if all_runtime_verified else "structurally_supported_unverified")
        )
        operation_reports.append(
            {
                "operation_id": op.id,
                "kind": op.kind,
                "status": status,
                "supporting_nodes": sorted(set(path_nodes)),
                "diagnostics": diags,
            }
        )

    # Evaluate every acceptance criterion
    criteria_reports: list[dict[str, Any]] = []
    for link in ir.criteria_links:
        diags: list[str] = []
        missing_nodes = [nid for nid in link.node_ids if nid not in nodes]
        if missing_nodes:
            diags.append(f"missing_linked_nodes:{missing_nodes}")
        for oid in link.operation_ids:
            for d in op_diagnostics.get(oid, []):
                diags.append(f"operation({oid}):{d}")

        low = link.criterion_text.casefold()
        if any(k in low for k in ("replay", "odbudow", "histori")):
            if not any(n.node.role == "event_store" and n.node.properties.get("replayable") is True for n in ir.nodes):
                diags.append("missing_replayable_event_store")
            if not any(
                n.node.role == "projector" and n.node.properties.get("replay_side_effect_free") is True
                for n in ir.nodes
            ):
                diags.append("missing_side_effect_free_projector")
        if any(k in low for k in ("czas", "time", "urt", "uritime")):
            if not any(n.node.role == "temporal_service" for n in ir.nodes):
                diags.append("missing_temporal_service_node")

        supporting_nodes = sorted({nid for nid in link.node_ids if nid in nodes})
        if diags:
            status = "gap_detected"
        elif link.evidence_level in {"contract_verified", "integration_verified"}:
            status = "evidence_verified"
        else:
            status = "structurally_supported_unverified"

        criteria_reports.append(
            {
                "criterion_index": link.criterion_index,
                "criterion_text": link.criterion_text,
                "status": status,
                "operation_ids": link.operation_ids,
                "supporting_nodes": supporting_nodes,
                "diagnostics": sorted(set(diags)),
                "runtime_attested": status == "evidence_verified",
            }
        )

    has_gaps = any(c["status"] == "gap_detected" for c in criteria_reports) or any(
        o["status"] == "gap_detected" for o in operation_reports
    ) or not validation.valid

    return {
        "schema_version": "archpat.coverage/v1",
        "story_id": ir.story.id,
        "graph_id": ir.id,
        "variant": ir.variant,
        "semantic_hash": semantic_hash(ir),
        "structurally_complete": not has_gaps,
        "runtime_verified": (not has_gaps) and all(c["runtime_attested"] for c in criteria_reports),
        "operations": operation_reports,
        "acceptance_criteria": criteria_reports,
        "validation_errors": [f.model_dump(mode="json") for f in validation.errors],
        "note": "Structural path coverage never upgrades unverified proposals to runtime_verified.",
    }


def as_is_to_be_delta(
    target: ArchitectureGraph | ArchitectureIRv2,
    inventories: list[dict[str, Any]],
) -> dict[str, Any]:
    """ARP-005: Compare observed code2llm inventories (as-is) against target ArchitectureGraph (to-be)."""
    ir = _as_v2(target)
    matched_nodes: list[dict[str, Any]] = []
    new_proposed_nodes: list[dict[str, Any]] = []
    mapped_module_paths: set[str] = set()

    for item in ir.nodes:
        node = item.node
        if node.role == "actor":
            continue
        candidates: list[dict[str, Any]] = []
        for inv in inventories:
            for hit in match_reuse(inv, node.capability)[:3]:
                candidates.append(
                    {
                        "project": hit.get("project", inv.get("project", "unknown")),
                        "path": hit["path"],
                        "score": hit["score"],
                        "symbols": hit.get("symbols", [])[:8],
                        "evidence": "indexed_only",
                        "api_verified": False,
                    }
                )
                mapped_module_paths.add(f"{hit.get('project', inv.get('project', 'unknown'))}:{hit['path']}")
        if candidates:
            matched_nodes.append(
                {
                    "node_id": node.id,
                    "role": node.role,
                    "capability": node.capability,
                    "action": "verify_and_adapt",
                    "evidence_level": item.evidence_level,
                    "candidates": candidates,
                }
            )
        else:
            new_proposed_nodes.append(
                {
                    "node_id": node.id,
                    "role": node.role,
                    "capability": node.capability,
                    "action": "introduce_new_component",
                    "evidence_level": "proposed",
                }
            )

    total_as_is_modules = sum(len(inv.get("modules", [])) for inv in inventories)
    unmapped_count = max(0, total_as_is_modules - len(mapped_module_paths))

    return {
        "schema_version": "archpat.as-is-to-be-delta/v1",
        "story_id": ir.story.id,
        "target_graph_id": ir.id,
        "target_variant": ir.variant,
        "target_semantic_hash": semantic_hash(ir),
        "as_is_sources": [
            {
                "project": inv.get("project", "unknown"),
                "sha256": inv.get("sha256"),
                "parsed_modules": len(inv.get("modules", [])),
            }
            for inv in inventories
        ],
        "matched_target_nodes": matched_nodes,
        "new_proposed_nodes": new_proposed_nodes,
        "as_is_summary": {
            "total_observed_modules": total_as_is_modules,
            "mapped_modules": len(mapped_module_paths),
            "unmapped_modules": unmapped_count,
            "unused_proof": False,
            "note": "Absence of a static mapping is never proof that an existing module is unused or removable.",
        },
        "applied": False,
    }
