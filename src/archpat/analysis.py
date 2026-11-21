"""Proposal graph comparison and impact, independent of source-code execution."""
from __future__ import annotations

import networkx as nx
from .models import ArchitectureGraph
from .synthesis import fingerprint


def impact(graph: ArchitectureGraph, node_id: str) -> dict:
    if node_id not in {n.id for n in graph.nodes}:
        raise ValueError(f"Unknown graph node: {node_id}")
    dependencies = nx.DiGraph()
    dependencies.add_nodes_from(n.id for n in graph.nodes)
    # A depends_on B: changing B may affect A.
    dependencies.add_edges_from((e.target, e.source) for e in graph.edges if e.kind == "depends_on")
    flow = nx.DiGraph()
    flow.add_nodes_from(n.id for n in graph.nodes)
    flow.add_edges_from((e.source, e.target) for e in graph.edges
                        if e.kind in {"command", "query", "event", "write"})
    dependent_ids = sorted(nx.descendants(dependencies, node_id))
    flow_ids = sorted(nx.descendants(flow, node_id))
    return {"schema_version": "archpat.impact/v1", "node_id": node_id,
            "dependent_nodes": dependent_ids, "downstream_flow_nodes": flow_ids,
            "evidence": "proposed_graph_only", "source_code_impact_verified": False}


def diff_graphs(before: ArchitectureGraph, after: ArchitectureGraph) -> dict:
    def compare(old_items: list, new_items: list) -> dict:
        old = {x.id: x.model_dump(mode="json") for x in old_items}
        new = {x.id: x.model_dump(mode="json") for x in new_items}
        changed = []
        for key in sorted(old.keys() & new.keys()):
            fields = sorted(k for k in old[key] if old[key][k] != new[key][k])
            if fields:
                changed.append({"id": key, "changed_fields": fields})
        return {"added": sorted(new.keys() - old.keys()), "removed": sorted(old.keys() - new.keys()),
                "changed": changed, "unchanged": sorted(k for k in old.keys() & new.keys() if old[k] == new[k])}

    nodes = compare(before.nodes, after.nodes)
    edges = compare(before.edges, after.edges)
    return {"schema_version": "archpat.diff/v1",
            "baseline_sha256": fingerprint(before.model_dump(mode="json")),
            "target_sha256": fingerprint(after.model_dump(mode="json")),
            "nodes": nodes, "edges": edges,
            "potentially_breaking": bool(nodes["removed"] or edges["removed"] or nodes["changed"] or edges["changed"]),
            "evidence": "proposal_ir_comparison; not an imported code2schema/deconnected baseline",
            "next_steps": ["Verify source contracts at pinned revisions.",
                           "Map graph deltas to an isolated Forge proposal.",
                           "Run contract, replay and user-story acceptance tests before promotion."],
            "applied": False}

